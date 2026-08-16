photo_library(...): organizador de fotos local. Actions: status, scan, exif, group_by_date, thumbnails, find_by_date.
Requiere Pillow para exif y thumbnails (sin él -> needs_dependency). scan funciona SIN Pillow. group_by_date: subcarpetas YYYY-MM (o year/day) bajo output dir.
!= filesystem (sin awareness EXIF); != media_edit (edición video/audio, NO organización de fotos).
