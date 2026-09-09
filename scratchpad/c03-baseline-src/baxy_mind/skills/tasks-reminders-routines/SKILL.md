---
name: tasks-reminders-routines
description: Create, find, update, complete, restore, and schedule local tasks, reminders, and reusable routines without confusing their identities.
operations:
  - task.create
  - task.list
  - task.search
  - task.resolve.exact
  - task.update
  - task.complete
  - task.reopen
  - task.delete
  - task.restore
  - reminder.create
  - reminder.list
  - reminder.resolve.exact
  - reminder.delete
  - reminder.restore
  - routine.list
  - routine.read
  - routine.resolve.exact
  - routine.set.enabled
  - routine.delete
  - routine.restore
priority: 82
---
# Tasks, reminders, and routines

Choose the object named by the user: a task is actionable state, a reminder has
an explicit due instant, and a routine is a reusable definition. Resolve an
existing object exactly before update, completion, deletion, restore, or enable
changes; depend on that resolver and use only its opaque identity. Do not create
a reminder when time or timezone is ambiguous. A list/search operation is not
authorization to mutate every match.
