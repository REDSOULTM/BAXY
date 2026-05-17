Photo-library rule: photo_library(...) is a local photo organizer. Actions: status, scan, exif, group_by_date, thumbnails, find_by_date.

Requires Pillow for EXIF and thumbnails (returns needs_dependency without it). scan itself works without Pillow. group_by_date organizes photos into YYYY-MM (or year/day) subfolders under an output dir.

Distinct from filesystem(...) (no EXIF awareness) and from media_edit(...) (video / audio editing, not photo organization).
