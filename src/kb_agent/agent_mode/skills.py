import os
import json
import ast
import inspect
import importlib.util
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from kb_agent.config import settings
from kb_agent.agent_mode.sandbox import SandboxContext

@dataclass
class SkillInfo:
    name: str
    description: str
    parameters: Dict[str, Any]
    source_file: str
    # runtime
    execute_fn: Optional[Callable] = None

class SkillLoader:
    def __init__(self):
        self.skills: Dict[str, SkillInfo] = {}
        if settings and settings.skills_path:
            self.skills_dir = Path(settings.skills_path)
            # Create if doesn't exist but we might not have a Data Folder so handle gracefully
            try:
                self.skills_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                self.skills_dir = None
        else:
            self.skills_dir = None
            
        # Register built-ins directory
        self.builtin_dir = Path(__file__).parent / "builtin_skills"
        
    def scan(self):
        """Scan directories for skills and load them."""
        self.skills.clear()
        
        # Load built-ins first (so user skills can override if they happen to have same name)
        if self.builtin_dir.exists():
            self._load_dir(self.builtin_dir)
            
        # Load user skills
        if self.skills_dir and self.skills_dir.exists():
            self._load_dir(self.skills_dir)
            self._generate_manifest()
            
    def _parse_docstring_meta(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extract name, description, parameters from the module docstring."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            module = ast.parse(content)
            docstring = ast.get_docstring(module)
            if not docstring:
                return None
                
            meta = {}
            lines = docstring.strip().split("\n")
            
            # Very basic parser:
            # name: my_skill
            # description: Does something
            # parameters: {"arg1": "type"}
            for line in lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    key = parts[0].strip().lower()
                    val = parts[1].strip()
                    if key in ("name", "description"):
                        meta[key] = val
                    elif key == "parameters":
                        try:
                            # Try to parse it as JSON if possible
                            meta[key] = json.loads(val)
                        except json.JSONDecodeError:
                            meta[key] = {}
            return meta
        except Exception as e:
            return None

    def _load_dir(self, directory: Path):
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    file_path = Path(root) / file
                    self._load_skill(file_path)

    def _load_skill(self, file_path: Path):
        meta = self._parse_docstring_meta(file_path)
        if not meta or "name" not in meta or "description" not in meta:
            return
            
        try:
            name = meta["name"]
            spec = importlib.util.spec_from_file_location(f"skill_{name}", file_path)
            if not spec or not spec.loader:
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not hasattr(module, "execute") or not callable(module.execute):
                return
                
            skill_info = SkillInfo(
                name=name,
                description=meta["description"],
                parameters=meta.get("parameters", {}),
                source_file=str(file_path),
                execute_fn=module.execute
            )
            self.skills[name] = skill_info
        except Exception:
            pass

    def _generate_manifest(self):
        if not self.skills_dir:
            return
            
        manifest = []
        for name, info in self.skills.items():
            # Exclude built-in skills from the user manifest if they are not in skills_dir
            if not info.source_file.startswith(str(self.skills_dir)):
                continue
            manifest.append({
                "name": name,
                "description": info.description,
                "parameters": info.parameters,
                "source": info.source_file
            })
            
        manifest_path = self.skills_dir / "__manifest__.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception:
            pass
            
    def invoke(self, skill_name: str, kwargs: Dict[str, Any], sandbox: SandboxContext) -> Any:
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' not found")
            
        info = self.skills[skill_name]
        if not info.execute_fn:
            raise ValueError(f"Skill '{skill_name}' has no execute function")
            
        # Check if execute accepts sandbox
        sig = inspect.signature(info.execute_fn)
        if "sandbox" in sig.parameters:
            kwargs = kwargs.copy()
            kwargs["sandbox"] = sandbox
            
        return info.execute_fn(**kwargs)
