from __future__ import annotations

import os
from pathlib import Path

import yaml


class PromptLoader:
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)

    def load(self, name: str) -> dict:
        filepath = self.prompts_dir / f"{name}.yaml"
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def render(self, name: str, **kwargs) -> tuple[str, str]:
        from jinja2 import Template

        prompt = self.load(name)
        system_tpl = Template(prompt["system"])
        user_tpl = Template(prompt["user"])
        system_rendered = system_tpl.render(**kwargs)
        user_rendered = user_tpl.render(**kwargs)
        return system_rendered, user_rendered

    def list(self) -> list[str]:
        files = self.prompts_dir.glob("*.yaml")
        return [f.stem for f in files]
