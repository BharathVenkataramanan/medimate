from __future__ import annotations

import os
import sys
import threading
import webbrowser

from ddinter_lookup import DB_PATH
from rxnorm_catalog import CATALOG_PATH
from setup_reviewer import verify_ddinter, verify_rxnorm


def main():
    try:
        dd = verify_ddinter(DB_PATH)
        rx = verify_rxnorm(CATALOG_PATH)
    except Exception as exc:
        sys.exit('The reference databases are not ready: ' + str(exc) + '\nUse the full NUH ready-to-run package.')
    from server import PORT, main as serve
    print(f"References ready: {dd['pairs']} interaction records; {rx['concepts']} RxNorm concepts.")
    print('Fictional demonstration data only. No patient records have been provided.')
    if not os.environ.get('MEDIMATE_NO_BROWSER'):
        opener = threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}'))
        opener.daemon = True
        opener.start()
    serve()


if __name__ == '__main__':
    main()
