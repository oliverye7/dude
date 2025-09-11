# Available Tools

## bash_execute
Execute bash commands with permission control. Supports readonly mode (safe read commands only) and execute mode (allows write operations like mkdir, mv, etc.).

**Parameters:**
- `command` (required): The bash command to execute
- `permission` (optional): Permission level - 'readonly' for safe read commands only, 'execute' for write operations (defaults to 'readonly')
- `working_dir` (required): Working directory for command execution

**Usage Examples:**
```json
{
    "tool_name": "bash_execute",
    "tool_args": {
        "command": "ls -la",
        "permission": "readonly",
        "working_dir": "/path/to/project"
    }
}
```

```json
{
    "tool_name": "bash_execute", 
    "tool_args": {
        "command": "mkdir new_directory",
        "permission": "execute",
        "working_dir": "/path/to/project"
    }
}
```

**Important Notes:**
- Readonly mode allows: ls, cat, head, tail, grep, find, wc, sort, uniq, awk, sed, cut, pwd, which, file, stat, du, df, ps, top, whoami, id, date, uname, tree, less, more
- Execute mode allows all commands including write operations
- Commands timeout after 30 seconds
- Always use exact parameter names: "command", "permission", "working_dir"

---