Printer/scanner: printer_scanner(...) = print + scan local. Actions: status, printers_list, printer_default_get, printer_default_set, print_queue, print_file, cancel_job, scanners_list, scan_document, list.

- print_file: apunta a impresora específica intercambiando temporalmente la default + Start-Process -Verb Print.

Distinto de filesystem(...) (sin print) y document(...) (conversión, no print). Para imprimir/escanear físico = este tool. NO prometas comportamiento de servicios cloud print.
