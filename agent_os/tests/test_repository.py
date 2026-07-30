import os
import tempfile
import pytest
from agent_os.repository.repository import RepositoryKernel

def test_repository_kernel_scan_and_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a dummy workspace structure
        python_file = os.path.join(tmpdir, "main.py")
        js_file = os.path.join(tmpdir, "utils.js")
        ignored_dir = os.path.join(tmpdir, "node_modules")
        os.makedirs(ignored_dir)
        ignored_file = os.path.join(ignored_dir, "leftover.js")

        # Sample code contents
        python_code = """
import sys
from math import pi

class MyCalculator:
    def add(self, x, y):
        return x + y

async def compute_value():
    calc = MyCalculator()
    return calc.add(2, 3)
"""
        js_code = """
import { helper } from 'lib';
export class MathHelper {
    square(x) {
        return x * x;
    }
}
function runHelper() {
    console.log("Running JS helper");
}
"""
        with open(python_file, "w", encoding="utf-8") as f:
            f.write(python_code)
        with open(js_file, "w", encoding="utf-8") as f:
            f.write(js_code)
        with open(ignored_file, "w", encoding="utf-8") as f:
            f.write("console.log('ignored');")

        # 2. Instantiate and run scanner
        kernel = RepositoryKernel()
        kernel.scan_workspace(tmpdir)

        # 3. Verify files are listed and ignored list is respected
        files = kernel.list_files()
        assert "main.py" in files
        assert "utils.js" in files
        assert "node_modules/leftover.js" not in files

        # 4. Verify findFile (camelCase and snake_case)
        py_files = kernel.findFile("main.py")
        assert len(py_files) == 1
        assert py_files[0]["language"] == "python"

        # 5. Verify findClass
        calc_classes = kernel.find_class("MyCalculator")
        assert len(calc_classes) == 1
        assert calc_classes[0]["file_path"] == "main.py"

        js_classes = kernel.findClass("MathHelper")
        assert len(js_classes) == 1
        assert js_classes[0]["file_path"] == "utils.js"

        # 6. Verify findFunction
        funcs = kernel.find_function("add")
        assert len(funcs) == 1
        assert funcs[0]["file_path"] == "main.py"
        assert funcs[0]["type"] == "function"

        # 7. Verify findReferences
        refs = kernel.find_references("MyCalculator")
        assert len(refs) >= 1
        assert refs[0]["file_path"] == "main.py"
