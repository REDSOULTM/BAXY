Printer/scanner rule: printer_scanner(...) wraps local print + scan. Actions: status, printers_list, printer_default_get, printer_default_set, print_queue, print_file, cancel_job, scanners_list, scan_document, list.

print_file targets a specific printer by temporarily swapping the default and using Start-Process -Verb Print.

Distinct from filesystem(...) (no print pipeline) and from document(...) (file conversion, not print). When the user wants to physically print or scan, this is the tool — do not promise behavior of cloud print services.
