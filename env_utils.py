# env_utils.py
# this utility will check a students setup to verify it has
# packages loaded, python and or node installed and api keys available
# it references the pyproject.toml file and example.env for requirements

# ========== STANDARD LIBRARY IMPORTS ONLY (no external dependencies) ==========
import os
import sys
import shutil
import re
from pathlib import Path


# ========== EARLY PYTHON ENVIRONMENT DIAGNOSTICS ==========
def check_python_executable_and_version():
    """
    Check Python executable location and version BEFORE attempting any external imports.
    This ensures students get helpful diagnostics even if imports fail.

    Returns: tuple (success: bool, python_version_tuple, issues: list)
    """
    issues = []
    executable = Path(sys.executable).resolve()
    py_version = sys.version_info
    py_version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"

    print("=" * 70)
    print("PYTHON ENVIRONMENT DIAGNOSTICS")
    print("=" * 70)
    print(f"Python executable: {executable}")
    print(f"Python version: {py_version_str}")
    print(f"Platform: {sys.platform}")
    print()

    # Check if running in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

    # Check if executable is in expected .venv location
    cwd = Path.cwd()
    expected_venv = cwd / ".venv"

    # Platform-specific paths for venv Python
    if sys.platform == "win32":
        expected_python = expected_venv / "Scripts" / "python.exe"
    else:
        expected_python = expected_venv / "bin" / "python"

    executable_in_venv = False
    try:
        executable_in_venv = executable.resolve() == expected_python.resolve()
    except (OSError, RuntimeError):
        # Handle case where paths can't be resolved
        executable_in_venv = str(executable).startswith(str(expected_venv))

    if not in_venv:
        issues.append("⚠️  Not running in a virtual environment")
        issues.append("   This may cause import errors if required packages are not installed")
    elif not executable_in_venv:
        issues.append(f"⚠️  Python executable is not in expected .venv location")
        issues.append(f"   Expected: {expected_python}")
        issues.append(f"   Actual:   {executable}")
        issues.append("   You may be using a different virtual environment or system Python")
    else:
        print(f"✅ Running in virtual environment: {expected_venv}")

    # Check Python version against basic requirements (will verify against pyproject.toml later)
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 12):
        issues.append(f"⚠️  Python {py_version_str} is below minimum required version 3.12")
    elif py_version.major == 3 and py_version.minor >= 14:
        issues.append(f"⚠️  Python {py_version_str} is above maximum supported version (< 3.14)")
    else:
        print(f"✅ Python version {py_version_str} is in expected range (>=3.12, <3.14)")

    # Check sys.prefix and base_prefix
    print(f"\nEnvironment paths:")
    print(f"  sys.prefix:      {sys.prefix}")
    print(f"  sys.base_prefix: {sys.base_prefix}")
    if in_venv:
        print(f"  Virtual env:     {sys.prefix}")

    if issues:
        print("\n" + "!" * 70)
        print("POTENTIAL ISSUES DETECTED:")
        print("!" * 70)
        for issue in issues:
            print(issue)
        print("\nRECOMMENDATION:")
        print("  Run this script using: uv run python env_utils.py")
        print("  Or activate the virtual environment first:")
        if sys.platform == "win32":
            print("    .venv\\Scripts\\activate")
        else:
            print("    source .venv/bin/activate")
        print("!" * 70)

    print()
    return (len(issues) == 0, py_version, issues)


# ========== EXTERNAL DEPENDENCY IMPORTS (with error handling) ==========
try:
    from dotenv import dotenv_values, load_dotenv
    import tomllib
    from importlib import metadata
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    EXTERNAL_IMPORTS_AVAILABLE = True
except ImportError as e:
    EXTERNAL_IMPORTS_AVAILABLE = False
    IMPORT_ERROR = e
    print("=" * 70)
    print("IMPORT ERROR DETECTED")
    print("=" * 70)
    print(f"Failed to import required package: {e}")
    print()
    print("This usually means you're running Python outside the virtual environment")
    print("or the required packages are not installed.")
    print()
    print("SOLUTIONS:")
    print("  1. Run using uv (recommended):")
    print("       uv run python env_utils.py")
    print()
    print("  2. Activate the virtual environment first:")
    if sys.platform == "win32":
        print("       .venv\\Scripts\\activate")
    else:
        print("       source .venv/bin/activate")
    print("     Then run:")
    print("       python env_utils.py")
    print()
    print("  3. Install dependencies:")
    print("       uv sync")
    print("     or")
    print("       pip install -r requirements.txt")
    print("=" * 70)
    print()


def summarize_value(key: str, value: str, example_value: str = None) -> str:
    """Return masked form for API keys, or full value for non-API keys.

    Args:
        key: The environment variable name
        value: The current value
        example_value: The example/placeholder value from example.env (optional)

    Returns:
        - For *API_KEY variables: masked form (****last4) unless it matches the example value
        - For *API_KEY variables matching example: full value (to show it needs changing)
        - For non-API_KEY variables: full value (not obscured)
        - For boolean strings: lowercase boolean
    """
    lower = value.lower()
    if lower in ("true", "false"):
        return lower

    # Check if this is an API_KEY variable
    is_api_key = key.endswith("API_KEY")

    if not is_api_key:
        # Non-API_KEY variables are never obscured
        return value

    # For API_KEY variables, show full value if it matches the example (needs changing)
    if example_value and value == example_value:
        return value

    # Otherwise, obscure the API key
    return "****" + value[-4:] if len(value) > 4 else "****" + value

def check_env_conflicts(env_file_path: str):
    """Check for conflicts between system environment variables and .env file.

    This detects when users have API_KEYs in their system environment that may
    conflict with the ones they want to use from the .env file, since load_dotenv()
    does not override existing environment variables by default.

    Args:
        env_file_path: Path to the .env file
    """
    if not os.path.exists(env_file_path):
        return

    # Parse the .env file to get what values SHOULD be loaded
    from dotenv import dotenv_values
    env_file_vars = dotenv_values(env_file_path)

    conflicts = []
    for key, file_value in env_file_vars.items():
        # Check if this key already exists in the environment
        sys_value = os.environ.get(key)
        if sys_value is not None and sys_value != file_value:
            # There's a conflict - system env var exists and differs from .env file
            conflicts.append({
                'key': key,
                'system_value': sys_value,
                'file_value': file_value
            })

    if conflicts:
        print("=" * 70)
        print("⚠️  ENVIRONMENT VARIABLE CONFLICTS DETECTED")
        print("=" * 70)
        print("The following environment variables are already set in your system")
        print("environment and differ from your .env file. Since load_dotenv()")
        print("does not override existing variables, the system values will be used,")
        print("which may not be what you intended.")
        print()
        for conflict in conflicts:
            key = conflict['key']
            print(f"Variable: {key}")
            if key.endswith('API_KEY'):
                # Obscure API keys in the output
                sys_val = "****" + conflict['system_value'][-4:] if len(conflict['system_value']) > 4 else "****"
                file_val = "****" + conflict['file_value'][-4:] if len(conflict['file_value']) > 4 else "****"
                print(f"  System value: {sys_val}")
                print(f"  .env value:   {file_val}")
            else:
                print(f"  System value: {conflict['system_value']}")
                print(f"  .env value:   {conflict['file_value']}")
            print()

        print("SOLUTIONS:")
        print("  1. Unset the conflicting system environment variables:")
        if sys.platform == "win32":
            print("     CMD:")
            for conflict in conflicts:
                print(f"       set {conflict['key']}=")
            print("     PowerShell:")
            for conflict in conflicts:
                print(f"       Remove-Item Env:\\{conflict['key']}")
        else:
            for conflict in conflicts:
                print(f"       unset {conflict['key']}")
        print()
        print("  2. Use load_dotenv(override=True) in your notebooks to force")
        print("     .env values to take precedence")
        print()
        print("  3. Update your .env file to match your system environment")
        print("=" * 70)
        print()


def check_manual_installs(file_path: str):
    """Check if manually installed applications are available in PATH.

    Looks for a comment line like: # Manual installs for checking: app1, app2, app3

    Args:
        file_path: Path to the example.env file to check
    """
    if not os.path.exists(file_path):
        return

    manual_installs = []
    with open(file_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            # Look for the manual installs comment
            if stripped.startswith('# Manual installs for checking:'):
                # Extract the comma-delimited list after the colon
                apps_str = stripped.split(':', 1)[1].strip()
                if apps_str:
                    manual_installs = [app.strip() for app in apps_str.split(',')]
                break

    if not manual_installs:
        return

    # Check each application
    issues = []
    found = []

    for app in manual_installs:
        if shutil.which(app) is not None:
            found.append(f"✅ {app}")
        else:
            issues.append(f"⚠️  {app} not found in PATH")

    # Print results
    print("Manual Installs Check:")
    for item in found:
        print(item)
    for issue in issues:
        print(issue)
    print()


def doublecheck_env(file_path: str):
    """Check environment variables against an example env file and print summaries.

    Args:
        file_path: Path to the example.env file to check against
    """
    if not os.path.exists(file_path):
        print(f"Did not find file {file_path}.")
        print("This is used to double check the key settings for the notebook.")
        print("This is just a check and is not required.\n")
        return

    # Parse the example file to identify required keys and their example values
    required_keys = {}
    all_example_values = {}
    with open(file_path, 'r') as f:
        lines = f.readlines()
        is_required_section = False
        for line in lines:
            stripped = line.strip()
            # Check if this is a comment line
            if stripped.startswith('#'):
                # Check if comment contains "required" (case-insensitive)
                if 'required' in stripped.lower():
                    is_required_section = True
                else:
                    # A different comment section starts
                    is_required_section = False
            # Check if this is a key=value line
            elif '=' in stripped and not stripped.startswith('#'):
                key = stripped.split('=')[0].strip()
                value = stripped.split('=', 1)[1].strip()
                # Remove quotes if present
                if value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                all_example_values[key] = value
                if is_required_section:
                    required_keys[key] = value

    # Parse the example file to get all keys
    parsed = dotenv_values(file_path)
    issues = []

    print("Environment Variables:")
    printed_keys = set()

    for key in parsed.keys():
        current = os.getenv(key)
        example_val = all_example_values.get(key)

        if current is not None:
            # Use the new summarize_value with key, value, and example_value
            print(f"{key}={summarize_value(key, current, example_val)}")

            # Check if this required key still has the example/placeholder value
            if key in required_keys:
                if current == example_val:
                    issues.append(f"  ⚠️  {key} still has the example/placeholder value")
        else:
            print(f"{key}=<not set>")
            if key in required_keys:
                issues.append(f"  ⚠️  {key} is required but not set")

        printed_keys.add(key)

    # Check for any additional uncommented variables in .env that weren't in example.env
    actual_env_file = ".env"
    if os.path.exists(actual_env_file):
        actual_env_vars = dotenv_values(actual_env_file)
        additional_vars = set(actual_env_vars.keys()) - printed_keys

        if additional_vars:
            print("\nAdditional variables in .env (not in example.env):")
            for key in sorted(additional_vars):
                current = os.getenv(key)
                if current is not None:
                    # No example value to compare against for additional vars
                    print(f"{key}={summarize_value(key, current, None)}")
                else:
                    print(f"{key}=<not set>")

    # Special check for LangSmith tracing
    langsmith_tracing = os.getenv("LANGSMITH_TRACING", "").lower()
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_example = all_example_values.get("LANGSMITH_API_KEY", "")

    if langsmith_tracing == "true":
        # Check if API key is missing, empty, or still has the example value
        if not langsmith_api_key:
            issues.append(f"  ⚠️  LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is not set")
        elif langsmith_api_key == langsmith_example:
            issues.append(f"  ⚠️  LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY still has the example/placeholder value")

    # Print any issues found
    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(issue)
    print()


def check_venv(expected_venv_path: str = ".venv"):
    """Check if virtual environment is properly activated.

    Args:
        expected_venv_path: Expected path to the virtual environment (default: ".venv")
    """
    issues = []

    # Check sys.prefix - this is set to the venv path when activated
    current_prefix = Path(sys.prefix).resolve()
    expected_path_obj = Path(expected_venv_path).resolve()

    # Check if running in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

    if not in_venv:
        issues.append("⚠️  Virtual environment is not activated")
        issues.append("   Run: source .venv/bin/activate  (or .venv\\Scripts\\activate on Windows)")
    else:
        # Virtual env is activated, check if it's the expected one
        if current_prefix != expected_path_obj:
            issues.append(f"⚠️  Activated venv ({current_prefix}) doesn't match expected path ({expected_path_obj})")

    # Check if uv is available
    uv_available = shutil.which("uv") is not None

    if not uv_available:
        issues.append("ℹ️  'uv' command not found - this project recommends using uv for package management")
        issues.append("   Install uv: https://docs.astral.sh/uv/")

    # Print results
    if issues:
        print("Virtual Environment Check:")
        for issue in issues:
            print(issue)
        print()
    else:
        print("✅ Virtual environment is properly activated")
        if uv_available:
            print("✅ uv is available")
        print()


# ========== utility to check packages and python based on pyproject.toml  =====================================

def _fmt_row(cols, widths):
    return " | ".join(str(c).ljust(w) for c, w in zip(cols, widths))

def doublecheck_pkgs(pyproject_path="pyproject.toml", verbose=False):
    p = Path(pyproject_path)
    if not p.exists():
        print(f"ERROR: {pyproject_path} not found.")
        return None

    # Load pyproject + python requirement
    with p.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    python_spec_str = project.get("requires-python") or ">=3.11"

    py_ver = Version(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    py_ok = py_ver in SpecifierSet(python_spec_str)

    # Load deps (PEP 621)
    deps = project.get("dependencies", [])
    if not deps:
        if verbose or not py_ok:
            print("No [project].dependencies found in pyproject.toml.")
            print(f"Python {py_ver} {'satisfies' if py_ok else 'DOES NOT satisfy'} requires-python: {python_spec_str}")
            print(f"Executable: {sys.executable}")
        return None

    # Evaluate deps
    results = []
    problems = []
    for dep in deps:
        try:
            req = Requirement(dep)
            name = req.name
            spec = str(req.specifier) if req.specifier else "(any)"
        except Exception:
            name, spec = dep, "(unparsed)"

        rec = {"package": name, "required": spec, "installed": "-", "path": "-", "status": "❌ Missing"}

        try:
            installed_ver = metadata.version(name)
            rec["installed"] = installed_ver
            try:
                dist = metadata.distribution(name)
                rec["path"] = str(dist.locate_file(""))
            except Exception:
                rec["path"] = "(unknown)"

            # Check if package is in correct Python version's site-packages
            expected_py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            path_str = str(rec["path"]).lower()

            # Check for version mismatch in path (if path contains a python version)
            wrong_version = False
            if "python" in path_str and rec["path"] != "(unknown)":
                # Look for patterns like python3.11, python3.13, etc. that don't match current version
                py_versions_in_path = re.findall(r'python\d+\.\d+', path_str)
                if py_versions_in_path:
                    # If we found python version(s) in path, check if any match current version
                    if expected_py_version.lower() not in py_versions_in_path:
                        wrong_version = True
                        rec["status"] = "⚠️ Wrong Python version"

            if not wrong_version:
                if spec not in ("(any)", "(unparsed)") and any(op in spec for op in "<>="):
                    sset = SpecifierSet(spec)
                    if Version(installed_ver) in sset:
                        rec["status"] = "✅ OK"
                    else:
                        rec["status"] = "⚠️ Version mismatch"
                else:
                    rec["status"] = "✅ OK"

        except metadata.PackageNotFoundError:
            # keep defaults: installed "-", status "❌ Missing"
            pass

        results.append(rec)
        if rec["status"] != "✅ OK":
            problems.append(rec)

    should_print = verbose or (not py_ok) or bool(problems)
    if should_print:
        # Python status
        print(f"Python {py_ver} {'satisfies' if py_ok else 'DOES NOT satisfy'} requires-python: {python_spec_str}")

        # Table (no hints column)
        headers = ["package", "required", "installed", "status", "path"]
        def short_path(s, maxlen=80):
            s = str(s)
            return s if len(s) <= maxlen else ("…" + s[-(maxlen-1):])
        rows = [[r["package"], r["required"], r["installed"], r["status"], short_path(r["path"])] for r in results]
        widths = [max(len(h), *(len(str(row[i])) for row in rows)) for i, h in enumerate(headers)]
        print(_fmt_row(headers, widths))
        print(_fmt_row(["-"*w for w in widths], widths))
        for row in rows:
            print(_fmt_row(row, widths))

        # Summarize issues without prescribing a tool
        if problems:
            print("\nIssues detected:")
            for r in problems:
                print(f"- {r['package']}: {r['status']} (required {r['required']}, installed {r['installed']}, path {r['path']})")

        if verbose or problems or not py_ok:
            print("\nEnvironment:")
            print(f"- Executable: {sys.executable}")

    return None


if __name__ == "__main__":
    # Run early diagnostics FIRST (uses only standard library)
    success, py_version, issues = check_python_executable_and_version()

    # If external imports failed, exit with helpful message
    if not EXTERNAL_IMPORTS_AVAILABLE:
        print("Cannot proceed with full environment check due to missing dependencies.")
        print("Please follow the solutions above to fix the import errors.")
        sys.exit(1)

    # Proceed with remaining checks (require external dependencies)
    check_venv()
    check_manual_installs("example.env")

    # Check for environment conflicts BEFORE loading .env file
    # This detects when system env vars will override .env file values
    check_env_conflicts(".env")

    # Load environment variables from .env file
    load_dotenv()

    # Check environment variables and API keys
    doublecheck_env("example.env")

    # Check packages
    doublecheck_pkgs(pyproject_path="pyproject.toml", verbose=True)
