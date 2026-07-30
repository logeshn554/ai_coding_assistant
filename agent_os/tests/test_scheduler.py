import pytest
from agent_os.skills.scheduler import SkillScheduler
from agent_os.skills.plugins import (
    RenameSymbolSkill,
    GenerateTestSkill,
    FixImportSkill,
    ReviewPatchSkill,
    RefactorMethodSkill,
    OptimizeSQLSkill,
    UpdateDependencySkill
)

def test_skill_scheduler_registration_and_execution():
    scheduler = SkillScheduler()
    
    # Instantiate skill plugins
    rename_skill = RenameSymbolSkill()
    fix_import_skill = FixImportSkill()
    test_gen_skill = GenerateTestSkill()

    # 1. Register skills under task states
    scheduler.register_skill("EDIT", rename_skill)
    scheduler.register_skill("EDIT", fix_import_skill)
    scheduler.register_skill("TEST", test_gen_skill)

    # 2. Verify state retrieval
    edit_skills = scheduler.get_skills_for_state("EDIT")
    assert len(edit_skills) == 2
    assert edit_skills[0].name == "Rename Symbol"
    assert edit_skills[1].name == "Fix Import"

    test_skills = scheduler.get_skills_for_state("TEST")
    assert len(test_skills) == 1
    assert test_skills[0].name == "Generate Test"

    # 3. Verify sequential execution on context
    context = {"logs": []}
    updated_context = scheduler.schedule_skills("EDIT", context)

    # Both EDIT skills must be executed
    assert updated_context.get("rename_symbol_executed") is True
    assert updated_context.get("fix_import_executed") is True
    assert len(updated_context["logs"]) == 2
    assert updated_context["logs"][0] == "Renamed symbol successfully."
    assert updated_context["logs"][1] == "Resolved import linkages successfully."

    # Execute TEST skills
    final_context = scheduler.schedule_skills("TEST", updated_context)
    assert final_context.get("generate_test_executed") is True
    assert len(final_context["logs"]) == 3
    assert final_context["logs"][2] == "Generated test cases successfully."

def test_all_independent_skills_execute():
    # Instantiate all 7 example skills and verify they execute successfully on context
    skills = [
        RenameSymbolSkill(),
        GenerateTestSkill(),
        FixImportSkill(),
        ReviewPatchSkill(),
        RefactorMethodSkill(),
        OptimizeSQLSkill(),
        UpdateDependencySkill()
    ]
    
    context = {}
    for skill in skills:
        context = skill.execute(context)
        
    assert context.get("rename_symbol_executed") is True
    assert context.get("generate_test_executed") is True
    assert context.get("fix_import_executed") is True
    assert context.get("review_patch_executed") is True
    assert context.get("refactor_method_executed") is True
    assert context.get("optimize_sql_executed") is True
    assert context.get("update_dependency_executed") is True
    assert len(context.get("logs", [])) == 7
