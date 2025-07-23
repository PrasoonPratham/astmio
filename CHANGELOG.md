1.0.1 (2025-01-XX)
--------------------

- **Pydantic v2 Compatibility & Bug Fixes**:
  - Fixed Pydantic field name validation issues by converting private attributes to use `PrivateAttr`
  - Updated all structured logging calls to use standard Python logging format strings
  - Enhanced profile validation system to handle both dictionary and string field mappings
  - Improved message splitting logic with graceful error handling and fallback behavior
  - Fixed test assertions to match updated validation error messages
  - Added missing fields to `ParserConfig` class (`patient_name_field`, `sample_id_field`, `test_separator`, `component_separator`)
  - Enhanced `validate_profile()` function to preserve error details while maintaining backward compatibility
  - Full compatibility with modern Python and Pydantic versions while preserving existing API

1.0.0 (2025-06-17)
--------------------

- **Major Parser Overhaul & Modernization (v1.0.0)**:
  - The ASTM parser is now significantly more robust and flexible.
  - Added full support for messages with missing frame numbers.
  - Added full support for messages ending with `CR` instead of `CRLF`.
  - Checksum failures now log a warning instead of crashing the parser.
  - All Python 2 compatibility code has been removed (`compat.py`, etc.).
  - The library is now pure Python 3, ensuring future compatibility.
  - The codebase has been cleaned and simplified.

0.8.1 (2025-06-17)
--------------------

- Fix parsing of messages with missing frame number.

Release 0.5 (2013-03-16)
------------------------

- Rewrite emitter for Client: replace mystic sessions that hides some detail
  with explicit need of yielding Header and Terminator records;
- Fix emitter usage with infinity loop;
- Use timer based on scheduled tasks instead of threading.Timer;
- Remove internal states routine;
- Improve overall stability;
- Client now able to send data by chunks and with bulk mode, sending all records
  with single message;
- Code cleanup;

Release 0.4.1 (2013-02-01)
--------------------------

- Fix timer for Python 2.x

Release 0.4 (2013-02-01)
------------------------

- Fix astm.codec module: now it only decodes bytes to unicode and encodes
  unicode to bytes;
- Add records dispatcher for server request handler;
- Add session support for astm client emitter;
- Repeat ENQ on timeout;
- Code cleanup and refactoring;
- Set minimal Python version to 2.6, but 3.2-3.3 also works well.

Release 0.3 (2012-12-15)
------------------------

- Refactor OmniLab module;
- Rename astm.proto module to astm.protocol;
- Add support for network operation timeouts;
- Client now better communicates with ASTM records emitter;
- Improve logging;
- Code cleanup;
- More tests for base functionality.


Release 0.2 (2012-12-11)
------------------------

- Fork, mix and refactor asyncore/asynchat modules to astm.asynclib module which
  provides more suitable methods to implement asynchronous operations for our
  task;
- Implement ASTM client and server that handles common protocol routines.


Release 0.1 (2012-12-09)
------------------------

- Base decode/encode functions for ASTM data format;
- Small object model mapping based on couchdb-python solution that helps to
  design records as classes, access to fields by name alias and provide
  autoconversion between Python objects and ASTM raw values;
- Add demo support of OmniLab LabOnline product.
