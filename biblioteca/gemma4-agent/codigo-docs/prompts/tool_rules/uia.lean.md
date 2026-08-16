uia(...) = Windows UI Automation, the structured way to interact with standard app controls. Actions: tree, find, click, focus, set_value.

PREFER uia OVER gui(...) clicks whenever the target is a standard Windows control (button, edit, combo, list item, menu, tree node). uia returns names, control types, automation ids, bounds and clickable points -> far more stable than pixel coordinates.

Use window/title to scope a uia find to one app's tree. Fall back to gui(...) ONLY when uia returns nothing for the target.
