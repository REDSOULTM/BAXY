---
name: software-packages
description: Resolve an exact Windows package and perform a reviewable two-phase winget installation.
operations:
  - package.install.prepare
  - package.install.commit
priority: 86
---
# Windows package installation

Use `package.install.prepare` with the literal package ID and optional literal
version. It must resolve exactly one signed winget manifest without installing.
`package.install.commit` depends on the prepare result and consumes its opaque
confirmation identity only after installation confirmation. Never replace the
package ID with a fuzzy search result, accept source agreements silently, or
claim success without a winget receipt and post-install observation.
