#!/usr/bin/env python3
"""
Fix numpy compatibility issue in saved models
"""

import joblib
import numpy as np
from pathlib import Path

# Fix numpy random state issue
np.random.BitGenerator = np.random.bit_generator.BitGenerator

def fix_model(model_path):
    """Fix a single model file"""
    try:
        # Load with compatibility fix
        model = joblib.load(model_path)
        
        # Re-save with current numpy version
        joblib.dump(model, model_path)
        print(f"  [OK] Fixed: {model_path.name}")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to fix {model_path.name}: {e}")
        return False

def main():
    print("Fixing NumPy compatibility in models...")
    print("="*60)
    
    models_dir = Path("models/hybrid")
    
    # Fix all model files
    fixed = 0
    failed = 0
    
    for subdir in ["context", "microstructure", "meta_learner"]:
        subpath = models_dir / subdir
        if subpath.exists():
            print(f"\n{subdir.upper()}:")
            for model_file in subpath.glob("*.pkl"):
                if fix_model(model_file):
                    fixed += 1
                else:
                    failed += 1
    
    # Fix scalers
    print("\nSCALERS:")
    for scaler_file in models_dir.glob("scaler_*.pkl"):
        if fix_model(scaler_file):
            fixed += 1
        else:
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {fixed} fixed, {failed} failed")
    
    if failed == 0:
        print("[SUCCESS] All models fixed successfully!")
    else:
        print("[WARNING] Some models could not be fixed. May need retraining.")

if __name__ == "__main__":
    main()