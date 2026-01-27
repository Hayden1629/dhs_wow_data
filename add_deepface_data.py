"""
Add DeepFace analysis data to mugshots.json entries.
Processes each entry that has a local picture file and adds deepface analysis results.
Resumable - saves progress incrementally and skips already processed entries.
"""
import os
import json
import sys
from pathlib import Path
from datetime import datetime

# Suppress TensorFlow GPU/CUDA log spam
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_CPP_MIN_VLOG_LEVEL"] = "3"

if os.environ.get("DEEPFACE_CPU_ONLY", "").lower() in ("1", "true", "yes"):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from deepface import DeepFace


def _f(x, decimals: int = 1):
    """Convert numpy scalar to float for display."""
    try:
        return round(float(x), decimals)
    except (TypeError, ValueError):
        return x


def analyze_image(image_path: str):
    """Run DeepFace analysis on an image and return formatted results."""
    try:
        result = DeepFace.analyze(
            img_path=image_path,
            actions=["age", "gender", "race", "emotion"]
        )
        
        # Handle both single dict and list of dicts
        face = result[0] if isinstance(result, list) else result
        
        # Extract data in the format shown in terminal output
        deepface_data = {
            "age": int(face.get("age", 0)),
            "gender": {
                "dominant": face.get("dominant_gender", ""),
                "confidence": _f(face.get("gender", {}).get(face.get("dominant_gender", ""), 0), 1)
            },
            "race": {
                "dominant": face.get("dominant_race", ""),
                "confidence": _f(face.get("race", {}).get(face.get("dominant_race", ""), 0), 1)
            },
            "emotion": {
                "dominant": face.get("dominant_emotion", ""),
                "confidence": _f(face.get("emotion", {}).get(face.get("dominant_emotion", ""), 0), 1)
            },
            "face_confidence": _f(face.get("face_confidence", 0), 2)
        }
        
        return deepface_data
    except Exception as e:
        print(f"Error analyzing {image_path}: {e}", file=sys.stderr)
        return None


def save_json(json_path, data):
    """Save JSON file with atomic write (write to temp file then rename)."""
    temp_path = json_path.with_suffix('.json.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_path.replace(json_path)


def log_entry(log_file, entry_id, name, status, message=""):
    """Log an entry processing attempt."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file.write(f"{timestamp} | {entry_id} | {name} | {status}")
    if message:
        log_file.write(f" | {message}")
    log_file.write("\n")
    log_file.flush()


def main():
    script_dir = Path(__file__).parent
    json_path = script_dir / "output" / "mugshots.json"
    log_path = script_dir / "output" / "deepface_processing.log"
    
    if not json_path.exists():
        print(f"Error: {json_path} not found", file=sys.stderr)
        sys.exit(1)
    
    # Load JSON
    print(f"Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total = len(data)
    processed = 0
    already_done = 0
    skipped_no_pic = 0
    errors = 0
    
    # Open log file in append mode
    log_file = open(log_path, 'a', encoding='utf-8')
    log_entry(log_file, "SESSION", "START", "Session started", f"Total entries: {total}")
    
    print(f"Processing {total} entries...")
    print(f"Log file: {log_path}")
    print(f"Saving progress incrementally (every successful analysis)\n")
    
    # Process each entry
    for i, entry in enumerate(data, 1):
        entry_id = entry.get("ID", f"entry_{i}")
        entry_name = entry.get("NAME", "Unknown")
        
        # Skip if already processed
        if "DEEPFACE" in entry:
            already_done += 1
            if i % 100 == 0:  # Print progress every 100 entries
                print(f"[{i}/{total}] Already processed: {already_done}, New: {processed}, Skipped: {skipped_no_pic}, Errors: {errors}")
            continue
        
        picture_local = entry.get("PICTURE_LOCAL")
        
        if not picture_local:
            skipped_no_pic += 1
            log_entry(log_file, entry_id, entry_name, "SKIPPED", "No PICTURE_LOCAL")
            continue
        
        # Check if file exists
        image_path = Path(picture_local)
        if not image_path.exists():
            skipped_no_pic += 1
            log_entry(log_file, entry_id, entry_name, "SKIPPED", f"File not found: {image_path}")
            continue
        
        # Run deepface analysis
        print(f"[{i}/{total}] Processing: {entry_name}...", end=" ", flush=True)
        deepface_data = analyze_image(str(image_path))
        
        if deepface_data:
            entry["DEEPFACE"] = deepface_data
            processed += 1
            print("✓")
            log_entry(log_file, entry_id, entry_name, "SUCCESS", f"Age: {deepface_data['age']}, Gender: {deepface_data['gender']['dominant']}")
            
            # Save JSON after each successful analysis
            save_json(json_path, data)
        else:
            errors += 1
            print("✗ (error)")
            log_entry(log_file, entry_id, entry_name, "ERROR", "DeepFace analysis failed")
    
    log_file.close()
    
    print(f"\n{'='*60}")
    print(f"Complete!")
    print(f"  Already processed: {already_done}")
    print(f"  Newly processed: {processed}")
    print(f"  Skipped (no picture): {skipped_no_pic}")
    print(f"  Errors: {errors}")
    print(f"  Total: {total}")
    print(f"  Log saved to: {log_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
