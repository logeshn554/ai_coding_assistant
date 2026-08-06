import os
import tempfile
import shutil
import pytest
from agent_os.repository.repository import RepositoryKernel

def test_lsp_diagnostics_integration():
    # Setup temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_repo.db")
    
    try:
        repo = RepositoryKernel(db_path=db_path)
        repo.workspace_root = temp_dir
        
        # 1. Create a dummy file and scan it to create class/function symbol records
        file_content = (
            "class MyDummyClass:\n"
            "    def dummy_func(self):\n"
            "        x = 10\n"
            "        return x\n"
        )
        rel_path = "dummy.py"
        repo.write_file(rel_path, file_content)
        repo.scan_workspace(temp_dir)
        
        # Verify symbols exist
        cls_symbols = repo.find_class("MyDummyClass")
        assert len(cls_symbols) > 0
        func_symbols = repo.find_function("dummy_func")
        assert len(func_symbols) > 0
        
        # 2. Store LSP diagnostics for this file
        diagnostics = [
            {
                "severity": 1,
                "message": "SyntaxError: invalid syntax",
                "line": 2,  # inside dummy_func (lines 2-4)
                "character": 5,
                "code": "E999",
                "source": "pyright"
            },
            {
                "severity": 2,
                "message": "Unused variable 'y'",
                "line": 6,  # outside any symbol
                "character": 1,
                "code": "W111",
                "source": "pyright"
            }
        ]
        repo.store_lsp_diagnostics(rel_path, diagnostics)
        
        # 3. Retrieve diagnostics for the file
        file_diags = repo.get_lsp_diagnostics(rel_path)
        assert len(file_diags) == 2
        assert file_diags[0]["message"] == "SyntaxError: invalid syntax"
        assert file_diags[0]["line"] == 2
        assert file_diags[0]["code"] == "E999"
        
        # 4. Query diagnostics for the function symbol
        func_diags = repo.get_symbol_diagnostics("dummy_func")
        assert len(func_diags) == 1
        assert func_diags[0]["message"] == "SyntaxError: invalid syntax"
        assert func_diags[0]["line"] == 2
        
        # 5. Query diagnostics for the class symbol (spans lines 1 to 4, contains dummy_func)
        cls_diags = repo.get_symbol_diagnostics("MyDummyClass")
        assert len(cls_diags) == 1
        assert cls_diags[0]["message"] == "SyntaxError: invalid syntax"
        assert cls_diags[0]["line"] == 2

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
