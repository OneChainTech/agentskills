#!/usr/bin/env python3
"""
Quick validation script for skills - enforces standard directory structure and metadata.
"""
import sys
import os
import re
from pathlib import Path

def validate_skill(skill_path):
    """Basic validation of a skill directory structure and SKILL.md content."""
    skill_path = Path(skill_path).resolve()
    
    # Check if SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, f"Missing required file: {skill_path.name}/SKILL.md"
    
    # Read and validate content
    try:
        content = skill_md.read_text(encoding='utf-8')
    except Exception as e:
        return False, f"Failed to read SKILL.md: {e}"
        
    if not content.startswith('---'):
        return False, "SKILL.md must start with YAML frontmatter delimited by '---'"
    
    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format in SKILL.md (missing closing '---')"
    
    frontmatter = match.group(1)
    
    # Check required metadata fields
    if 'name:' not in frontmatter:
        return False, "Missing 'name' field in frontmatter"
    if 'description:' not in frontmatter:
        return False, "Missing 'description' field in frontmatter"
    
    # Validate skill name format (hyphen-case)
    name_match = re.search(r'name:\s*([^\n]+)', frontmatter)
    if name_match:
        name = name_match.group(1).strip().strip('"').strip("'")
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Skill name '{name}' must be hyphen-case (lowercase letters, digits, and hyphens only)"
        if name != skill_path.name:
            return False, f"Skill name '{name}' in metadata must match directory name '{skill_path.name}'"
            
    # Validate description (no HTML tags)
    desc_match = re.search(r'description:\s*([^\n]+)', frontmatter)
    if desc_match:
        description = desc_match.group(1).strip()
        if '<' in description or '>' in description:
            return False, "Description contains restricted characters (< or >)"

    # Check for recommended directories
    # (Optional: scripts/, references/, assets/)
    
    return True, "Skill structure and metadata are valid"

def main():
    if len(sys.argv) < 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
        
    valid, message = validate_skill(sys.argv[1])
    if valid:
        print(f"✅ {message}")
        sys.exit(0)
    else:
        print(f"❌ {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()
