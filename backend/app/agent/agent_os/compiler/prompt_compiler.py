import json
import re
from typing import Any

from agent_os.compiler.interfaces import IPromptCompiler


class PromptCompiler(IPromptCompiler):
    """Prompt Compiler optimizing and formatting prompt inputs tailored to different models."""
    
    def estimate_tokens(self, prompt: str) -> int:
        return len(prompt) // 4

    def compile_prompt(
        self,
        task: str,
        repository_objects: list[dict[str, Any]],
        context: str,
        artifacts: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        system_prompt: str,
        model_name: str = "default"
    ) -> str:
        model_name = model_name.lower()
        
        # 1. Extract keywords for relevance prioritizing
        keywords = set(re.findall(r'\b[A-Za-z0-9_]+\b', task.lower()))
        
        # 2. Prioritize & Deduplicate Repository Objects
        prioritized_objects = []
        for obj in repository_objects:
            obj_name = obj.get("name", "")
            # Skip if object is already explicitly mentioned or printed inside context payload
            if obj_name and obj_name in context:
                continue
                
            score = 0
            if obj_name:
                score += sum(2 for kw in keywords if kw in obj_name.lower())
            sig = obj.get("signature", "")
            if sig:
                score += sum(1 for kw in keywords if kw in sig.lower())
                
            prioritized_objects.append((score, obj))
            
        # Sort by score descending
        prioritized_objects.sort(key=lambda x: x[0], reverse=True)
        sorted_objs = [x[1] for x in prioritized_objects]

        # 3. Prioritize & Deduplicate Diagnostics
        dedup_diagnostics = []
        seen_diag = set()
        for diag in diagnostics:
            msg = diag.get("message", "")
            path = diag.get("file_path", "")
            diag_key = f"{path}:{msg}"
            if diag_key in seen_diag:
                continue
            seen_diag.add(diag_key)
            
            score = sum(1 for kw in keywords if kw in msg.lower() or kw in path.lower())
            dedup_diagnostics.append((score, diag))
            
        dedup_diagnostics.sort(key=lambda x: x[0], reverse=True)
        sorted_diags = [x[1] for x in dedup_diagnostics]

        # 4. Compile into target formats
        if "anthropic" in model_name or "claude" in model_name:
            return self._compile_xml(
                task, sorted_objs, context, artifacts, sorted_diags, system_prompt
            )
        elif "openai" in model_name or "gpt" in model_name:
            return self._compile_markdown_json(
                task, sorted_objs, context, artifacts, sorted_diags, system_prompt
            )
        else:
            return self._compile_generic(
                task, sorted_objs, context, artifacts, sorted_diags, system_prompt
            )

    def _compile_xml(
        self,
        task: str,
        objects: list[dict[str, Any]],
        context: str,
        artifacts: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        system: str
    ) -> str:
        obj_xml = []
        for o in objects:
            sig = o.get("signature") or o.get("name")
            obj_xml.append(f"  <object type=\"{o.get('type')}\" name=\"{o.get('name')}\">{sig}</object>")
        objects_str = "\n".join(obj_xml)

        diag_xml = []
        for d in diagnostics:
            diag_xml.append(f"  <diagnostic file=\"{d.get('file_path')}\" line=\"{d.get('line')}\" severity=\"{d.get('severity')}\">{d.get('message')}</diagnostic>")
        diags_str = "\n".join(diag_xml)

        art_xml = []
        for k, v in artifacts.items():
            art_xml.append(f"  <artifact name=\"{k}\">\n    {v}\n  </artifact>")
        arts_str = "\n".join(art_xml)

        return f"""<system_prompt>
{system}
</system_prompt>

<context>
{context}
</context>

<repository_objects>
{objects_str}
</repository_objects>

<diagnostics>
{diags_str}
</diagnostics>

<artifacts>
{arts_str}
</artifacts>

<task>
{task}
</task>"""

    def _compile_markdown_json(
        self,
        task: str,
        objects: list[dict[str, Any]],
        context: str,
        artifacts: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        system: str
    ) -> str:
        # Compact formatting
        objs_json = json.dumps([{"name": o.get("name"), "type": o.get("type"), "signature": o.get("signature")} for o in objects], ensure_ascii=False)
        diags_json = json.dumps([{"file": d.get("file_path"), "msg": d.get("message"), "severity": d.get("severity")} for d in diagnostics], ensure_ascii=False)
        arts_json = json.dumps(artifacts, ensure_ascii=False)

        return f"""# SYSTEM INSTRUCTIONS
{system}

# CONTEXT STATE
{context}

# REPOSITORY SIGNATURES
{objs_json}

# DIAGNOSTICS
{diags_json}

# ARTIFACTS
{arts_json}

# USER TASK
{task}"""

    def _compile_generic(
        self,
        task: str,
        objects: list[dict[str, Any]],
        context: str,
        artifacts: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        system: str
    ) -> str:
        objs_str = "\n".join(f"- [{o.get('type')}] {o.get('name')}: {o.get('signature')}" for o in objects)
        diags_str = "\n".join(f"- [{d.get('severity')}] {d.get('file_path')}:{d.get('line')} - {d.get('message')}" for d in diagnostics)
        arts_str = "\n".join(f"## {k}\n{v}" for k, v in artifacts.items())

        return f"""=== SYSTEM INSTRUCTIONS ===
{system}

=== CONTEXT STATE ===
{context}

=== REPOSITORY OBJECTS ===
{objs_str}

=== DIAGNOSTICS ===
{diags_str}

=== ARTIFACTS ===
{arts_str}

=== USER TASK ===
{task}"""
