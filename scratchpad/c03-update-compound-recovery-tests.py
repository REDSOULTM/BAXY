import ast
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for relative in ['tests/test_turn_policy.py','tests/test_compound_missions.py']:
    path=root/relative
    source=path.read_text(encoding='utf-8');lines=source.splitlines(keepends=True)
    edits=[]
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node,ast.FunctionDef):continue
        calls=[statement for statement in node.body if isinstance(statement,ast.Assign)
               and isinstance(statement.value,ast.Call)
               and isinstance(statement.value.func,ast.Name)
               and statement.value.func.id=='apply_compound_effect_conservation_veto']
        if not calls:continue
        assignment=calls[0];target=assignment.targets[0].id
        assertions=[statement for statement in node.body if isinstance(statement,ast.Assert)
                    and any(isinstance(n,ast.Name) and n.id==target for n in ast.walk(statement))]
        # Only prior tests expecting the refused proposal to become conversation.
        if not any('conversation' in ast.unparse(a) for a in assertions):continue
        original=''.join(lines[assignment.lineno-1:assignment.end_lineno])
        call=original.replace(f'{target} = ', '', 1)
        replacement='    with pytest.raises(PlannerContractError, match="unresolved_compound_effects"):\n'+''.join('    '+line for line in call.splitlines(keepends=True))
        edits.append((assignment.lineno-1,assignment.end_lineno,replacement))
        edits.extend((a.lineno-1,a.end_lineno,'') for a in assertions)
        print(relative,node.name)
    for start,end,replacement in sorted(edits,reverse=True):lines[start:end]=[replacement]
    changed=''.join(lines)
    if relative.endswith('test_compound_missions.py'):
        changed=changed.replace('from pathlib import Path\n','from pathlib import Path\n\nimport pytest\n\nfrom baxy_mind.planner import PlannerContractError\n',1)
    path.write_text(changed,encoding='utf-8')
