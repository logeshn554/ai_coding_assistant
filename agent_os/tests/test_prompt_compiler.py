import pytest
from agent_os.compiler.prompt_compiler import PromptCompiler

def test_prompt_compiler_token_estimation():
    compiler = PromptCompiler()
    prompt = "This is a prompt of 28 chars"
    assert compiler.estimate_tokens(prompt) == 7

def test_prompt_compiler_prioritise_and_deduplicate():
    compiler = PromptCompiler()
    task = "Fix compile_prompt function in PromptCompiler class"
    
    # calc_sum is not relevant; compile_prompt is highly relevant
    repo_objs = [
        {"name": "calc_sum", "type": "function", "signature": "def calc_sum(x)"},
        {"name": "compile_prompt", "type": "function", "signature": "def compile_prompt(self, task)"},
        {"name": "StandardLogger", "type": "class", "signature": "class StandardLogger"}
    ]
    
    # 1. Verify prioritization: compile_prompt must rank first
    compiled = compiler.compile_prompt(
        task=task,
        repository_objects=repo_objs,
        context="",
        artifacts={},
        diagnostics=[],
        system_prompt="You are a helper",
        model_name="generic"
    )
    
    # In generic output format, compile_prompt should appear before calc_sum
    assert compiled.find("compile_prompt") < compiled.find("calc_sum")

    # 2. Verify deduplication with context: if a symbol is in context, skip it from definitions
    compiled_with_context = compiler.compile_prompt(
        task=task,
        repository_objects=repo_objs,
        context="Current function: compile_prompt",
        artifacts={},
        diagnostics=[],
        system_prompt="You are a helper",
        model_name="generic"
    )
    
    # Since compile_prompt is already in context, it shouldn't be added to REPOSITORY OBJECTS section
    repo_start = compiled_with_context.find("=== REPOSITORY OBJECTS ===")
    task_start = compiled_with_context.find("=== USER TASK ===")
    repo_section = compiled_with_context[repo_start:task_start]
    assert "compile_prompt" not in repo_section

def test_prompt_compiler_formats():
    compiler = PromptCompiler()
    task = "Implement di"
    repo_objs = [{"name": "DIContainer", "type": "class", "signature": "class DIContainer"}]
    diags = [{"file_path": "di.py", "line": 5, "severity": "error", "message": "SyntaxError"}]
    artifacts = {"task_list": "- Write container"}

    # Claude/Anthropic XML Format
    xml_prompt = compiler.compile_prompt(
        task=task,
        repository_objects=repo_objs,
        context="State initialized",
        artifacts=artifacts,
        diagnostics=diags,
        system_prompt="System instructions",
        model_name="claude"
    )
    assert "<system_prompt>" in xml_prompt
    assert "<repository_objects>" in xml_prompt
    assert "<diagnostics>" in xml_prompt
    assert "<artifacts>" in xml_prompt
    assert "<task>" in xml_prompt

    # OpenAI Markdown / JSON Format
    openai_prompt = compiler.compile_prompt(
        task=task,
        repository_objects=repo_objs,
        context="State initialized",
        artifacts=artifacts,
        diagnostics=diags,
        system_prompt="System instructions",
        model_name="gpt-4o"
    )
    assert "# SYSTEM INSTRUCTIONS" in openai_prompt
    assert "# CONTEXT STATE" in openai_prompt
    assert "# REPOSITORY SIGNATURES" in openai_prompt
    assert "DIContainer" in openai_prompt
