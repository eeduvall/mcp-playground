#!/usr/bin/env python3
"""
Module 1: Basic MCP Server - Starter Code
TODO: Implement tools for analyzing git changes and suggesting PR templates
"""

import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("pr-agent")

# PR template directory (shared across all modules)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


# TODO: Implement tool functions here
# Example structure for a tool:
# @mcp.tool()
# async def analyze_file_changes(base_branch: str = "main", include_diff: bool = True) -> str:
#     """Get the full diff and list of changed files in the current git repository.
#     
#     Args:
#         base_branch: Base branch to compare against (default: main)
#         include_diff: Include the full diff content (default: true)
#     """
#     # Your implementation here
#     pass

# Minimal stub implementations so the server runs
# TODO: Replace these with your actual implementations

@mcp.tool()
async def analyze_file_changes(base_branch: str = "main", include_diff: bool = True, max_diff_lines: int = 500) -> str:
    """Get the full diff and list of changed files in the current git repository.
    
    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
        max_diff_lines: Maximum number of diff lines to include (default: 500)
    """
    try:
        # Get Claude's working directory from roots
        context = mcp.get_context()
        roots_result = await context.session.list_roots()
        working_dir = roots_result.roots[0].uri.path
        
        # Get the diff
        diff_cmd = ["git", "diff", f"{base_branch}...HEAD"]
        diff_result = subprocess.run(
            diff_cmd,
            capture_output=True,
            text=True,
            cwd=working_dir
        )
        
        if diff_result.returncode != 0:
            return json.dumps({
                "error": f"Git diff command failed: {diff_result.stderr}",
                "command": " ".join(diff_cmd)
            })
        
        diff_output = diff_result.stdout
        diff_lines = diff_output.split('\n')
        total_lines = len(diff_lines)
        
        # Smart truncation if needed
        if total_lines > max_diff_lines:
            truncated_diff = '\n'.join(diff_lines[:max_diff_lines])
            truncated_diff += f"\n\n... Output truncated. Showing {max_diff_lines} of {total_lines} lines ..."
            diff_output = truncated_diff
        
        # Get summary statistics
        stats_cmd = ["git", "diff", "--stat", f"{base_branch}...HEAD"]
        stats_result = subprocess.run(
            stats_cmd,
            capture_output=True,
            text=True,
            cwd=working_dir
        )
        
        if stats_result.returncode != 0:
            return json.dumps({
                "error": f"Git diff --stat command failed: {stats_result.stderr}",
                "command": " ".join(stats_cmd)
            })
        
        # Get list of changed files
        files_cmd = ["git", "diff", "--name-status", f"{base_branch}...HEAD"]
        files_result = subprocess.run(
            files_cmd,
            capture_output=True,
            text=True,
            cwd=working_dir
        )
        
        if files_result.returncode != 0:
            return json.dumps({
                "error": f"Git diff --name-status command failed: {files_result.stderr}",
                "command": " ".join(files_cmd)
            })
        
        # Parse changed files
        changed_files = []
        for line in files_result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                status = parts[0]
                filename = parts[1]
                changed_files.append({"status": status, "filename": filename})
        
        # Build the response
        response = {
            "stats": stats_result.stdout,
            "total_diff_lines": total_lines,
            "files_changed": changed_files,
            "diff": diff_output if include_diff else "Diff not included (set include_diff=true to see it)"
        }
        
        return json.dumps(response)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    try:
        templates = {}
        
        # Check if templates directory exists
        if not TEMPLATES_DIR.exists() or not TEMPLATES_DIR.is_dir():
            return json.dumps({
                "error": f"Templates directory not found at {TEMPLATES_DIR}"
            })
        
        # Read all markdown files in the templates directory
        for template_file in TEMPLATES_DIR.glob("*.md"):
            try:
                # Get template name (filename without extension)
                template_name = template_file.stem
                
                # Read template content
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Add to templates dictionary
                templates[template_name] = {
                    "name": template_name,
                    "path": str(template_file),
                    "content": content
                }
                
            except Exception as e:
                # If one template fails, continue with others
                templates[template_file.name] = {
                    "name": template_file.name,
                    "error": f"Failed to read template: {str(e)}"
                }
        
        # Return templates as JSON
        return json.dumps({
            "templates": templates,
            "count": len(templates),
            "templates_dir": str(TEMPLATES_DIR)
        })
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.
    
    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    try:
        # Get all available templates first
        templates_json = await get_pr_templates()
        templates_data = json.loads(templates_json)
        
        # Check if there was an error getting templates
        if "error" in templates_data:
            return json.dumps({
                "error": f"Failed to get templates: {templates_data['error']}",
                "suggestion": None
            })
        
        # Check if we have any templates
        if templates_data.get("count", 0) == 0:
            return json.dumps({
                "error": "No templates available",
                "suggestion": None
            })
        
        templates = templates_data.get("templates", {})
        
        # Normalize the change type (lowercase)
        normalized_change_type = change_type.lower().strip()
        
        # Direct mapping for common change types
        common_types = {
            "bug": "bug",
            "fix": "bug",
            "bugfix": "bug",
            "feature": "feature",
            "feat": "feature",
            "enhancement": "feature",
            "docs": "docs",
            "documentation": "docs",
            "refactor": "refactor",
            "test": "test",
            "tests": "test",
            "testing": "test",
            "security": "security",
            "performance": "performance",
            "perf": "performance",
            "optimization": "performance"
        }
        
        # Try to find a direct match first
        suggested_template = common_types.get(normalized_change_type)
        
        # If we have a direct match and the template exists
        if suggested_template and suggested_template in templates:
            template = templates[suggested_template]
            return json.dumps({
                "suggestion": suggested_template,
                "template": template,
                "confidence": "high",
                "reason": f"Direct match for change type '{change_type}'"
            })
        
        # If no direct match or template doesn't exist, try to find the best match
        # based on the change summary and available templates
        
        # Fallback to a simple keyword matching approach
        keywords = {
            "bug": ["bug", "fix", "issue", "problem", "error", "crash", "resolve"],
            "feature": ["feature", "add", "new", "implement", "enhancement", "functionality"],
            "docs": ["docs", "documentation", "readme", "comment", "guide", "tutorial"],
            "refactor": ["refactor", "clean", "improve", "simplify", "restructure", "redesign"],
            "test": ["test", "coverage", "unit test", "integration test", "e2e", "testing"],
            "security": ["security", "vulnerability", "secure", "protect", "encrypt", "auth"],
            "performance": ["performance", "optimize", "speed", "efficient", "fast", "slow"]
        }
        
        # Count keyword occurrences in the changes summary
        scores = {template_type: 0 for template_type in keywords}
        summary_lower = changes_summary.lower()
        
        for template_type, words in keywords.items():
            for word in words:
                if word in summary_lower:
                    scores[template_type] += 1
        
        # Find the template type with the highest score
        best_match = max(scores.items(), key=lambda x: x[1])
        template_type, score = best_match
        
        # Only suggest if we have some match and the template exists
        if score > 0 and template_type in templates:
            template = templates[template_type]
            return json.dumps({
                "suggestion": template_type,
                "template": template,
                "confidence": "medium" if score > 2 else "low",
                "reason": f"Based on {score} keyword matches in the changes summary"
            })
        
        # If no good match found, default to feature template if available
        if "feature" in templates:
            return json.dumps({
                "suggestion": "feature",
                "template": templates["feature"],
                "confidence": "low",
                "reason": "No strong match found, defaulting to feature template"
            })
        
        # If feature template not available, use the first available template
        first_template_name = next(iter(templates))
        return json.dumps({
            "suggestion": first_template_name,
            "template": templates[first_template_name],
            "confidence": "low",
            "reason": "No match found, using first available template"
        })
        
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "suggestion": None
        })


if __name__ == "__main__":
    mcp.run()