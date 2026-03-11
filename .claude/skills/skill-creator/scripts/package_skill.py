#!/usr/bin/env python3
"""
Skill Packager - Creates a distributable .skill file of a skill folder

Usage:
    python scripts/package_skill.py <path/to/skill-folder> [output-directory]
"""

import fnmatch
import sys
import zipfile
from pathlib import Path
from quick_validate import validate_skill

# Directory patterns to exclude when packaging
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git", ".venv", "venv", ".pytest_cache"}
EXCLUDE_GLOBS = {"*.pyc", "*.pyo", "*.pyd", ".DS_Store", "*.swp"}
EXCLUDE_FILES = {".DS_Store", ".gitignore", ".env"}

# Directories excluded only at the skill root
ROOT_EXCLUDE_DIRS = {"evals", "tests"}

def should_exclude(rel_path: Path) -> bool:
    """Check if a path should be excluded from the package."""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    
    # rel_path is relative to skill_path.parent
    # so parts[0] is the skill folder name, parts[1] (if exists) is the first sub-dir
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
        
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
        
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)

def package_skill(skill_path, output_dir=None):
    """
    Package a skill folder into a .skill file.
    """
    skill_path = Path(skill_path).resolve()
    
    if not skill_path.exists():
        print(f"❌ Error: Skill folder not found: {skill_path}")
        return None
        
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"❌ Error: SKILL.md not found in {skill_path} (is this a skill folder?)")
        return None
        
    print("🔍 Validating skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"❌ Validation failed: {message}")
        return None
        
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve() / f"{skill_name}.skill"
    else:
        output_path = Path.cwd() / f"{skill_name}.skill"
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Packaging {skill_name} into {output_path}...")
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            base_path = skill_path.parent
            for file_path in skill_path.rglob('*'):
                rel_path = file_path.relative_to(base_path)
                
                if should_exclude(rel_path):
                    continue
                    
                if file_path.is_file():
                    zipf.write(file_path, rel_path)
                    
        print(f"✅ Created: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error: {e}")
        if output_path.exists():
            output_path.unlink()
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python package_skill.py <path/to/skill-folder> [output-directory]")
        sys.exit(1)
    
    package_skill(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

if __name__ == "__main__":
    main()
