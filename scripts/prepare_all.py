"""Run full dataset preparation: auto-label + YOLO structure + split."""
import sys
sys.path.insert(0, '.')

import json
import yaml
from vision.training.prepare_data import process_dataset
from vision.training.split_dataset import split_temporal_aware, validate_split

with open('configs/dataset.yaml') as f:
    config = yaml.safe_load(f)

print("Config loaded OK")
print(f"Sources: {[s['name'] for s in config['sources']]}")
print(f"Output: {config['output_dir']}")
print()

print("=== STEP 1: Auto-label + Dataset Prep ===")
print()
report = process_dataset(config)

print()
print("=== REPORT ===")
print(json.dumps(report, indent=2))
print()

if report["total_images"] == 0:
    print("ERROR: Zero images processed. Check dataset paths in configs/dataset.yaml")
    sys.exit(1)

print("=== STEP 2: Temporal-aware Split ===")
data_dir = config['output_dir']
stats = split_temporal_aware(data_dir, data_dir)

print(f"  Train: {stats.get('train', 0)} images ({stats.get('train_fire', 0)} fire, {stats.get('train_nofire', 0)} nofire)")
print(f"  Val:   {stats.get('val', 0)} images ({stats.get('val_fire', 0)} fire, {stats.get('val_nofire', 0)} nofire)")
print(f"  Test:  {stats.get('test', 0)} images ({stats.get('test_fire', 0)} fire, {stats.get('test_nofire', 0)} nofire)")
print()

print("=== STEP 3: Validate Split ===")
validation = validate_split(data_dir)
if validation["valid"]:
    print("Split validation PASSED")
else:
    print(f"Split validation FAILED: {validation['issues']}")
print()

print("=== DONE ===")
print(f"Dataset ready at: {config['output_dir']}")
print("Files:")
import os
for root, dirs, files in os.walk(config['output_dir']):
    level = root.replace(config['output_dir'], '').count(os.sep)
    indent = ' ' * 2 * (level + 1)
    print(f'{indent}{os.path.basename(root)}/')
    if level < 3:
        subindent = ' ' * 2 * (level + 2)
        for file in sorted(files)[:5]:
            print(f'{subindent}{file}')
        if len(files) > 5:
            print(f'{subindent}... ({len(files)} total)')
