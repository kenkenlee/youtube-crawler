"""Sanity check: verify videos.js has balanced braces/parens/brackets."""
src = open('static/js/videos.js', encoding='utf-8').read()
pairs = {'{': '}', '(': ')', '[': ']'}
stack = []
in_str = None
escape = False
line = 1
for ch in src:
    if ch == '\n':
        line += 1
    if escape:
        escape = False
    elif ch == '\\':
        escape = True
    elif in_str:
        if ch == in_str:
            in_str = None
    elif ch in ('"', "'", '`'):
        in_str = ch
    elif ch in pairs:
        stack.append((pairs[ch], line))
    elif ch in pairs.values():
        if not stack or stack[-1][0] != ch:
            print(f'MISMATCH at line {line}: got {ch}, expected {stack[-1][0] if stack else "nothing"}')
            break
        stack.pop()
else:
    if stack:
        print('UNCLOSED:', stack[-5:])
    else:
        print('JS structure OK, total lines:', line)
