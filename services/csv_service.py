import csv
import logging
from io import StringIO
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

ALLOWED_MODES = ["audit", "verified", "masters"]

def validate_csv_file(file_data: bytes) -> dict:
    """
    Phase C2: Validates the structural schema of the uploaded Open edX membership CSV.
    Checks headers, order sequence, file contents, and modes.
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "rows": [],
        "team_sets": []
    }

    # 1. Validate UTF-8 Encoding
    try:
        decoded_file = file_data.decode("utf-8")
    except UnicodeDecodeError:
        result["valid"] = False
        result["errors"].append("CSV file must be UTF-8 encoded.")
        return result

    # 2. Check for completely empty input
    if not decoded_file.strip():
        result["valid"] = False
        result["errors"].append("CSV file is empty.")
        return result

    csv_file = StringIO(decoded_file)
    reader = csv.DictReader(csv_file)

    # 3. Validate Header Existence
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        result["valid"] = False
        result["errors"].append("CSV header must contain at least 'user' and 'mode' columns.")
        return result

    # 4. Enforce strict specification sequence order: "user", then "mode"
    if reader.fieldnames[0] != "user" or reader.fieldnames[1] != "mode":
        result["valid"] = False
        result["errors"].append("Invalid header sequence. First column must be 'user' and second must be 'mode'.")
        return result

    # 5. Identify team-set columns (all columns after index 1)
    team_set_columns = reader.fieldnames[2:]
    result["team_sets"] = team_set_columns

    seen_users = set()
    has_rows = False

    # 6. Parse and Validate Rows
    for row_number, row in enumerate(reader, start=2):
        has_rows = True
        
        # Safely handle potential None values if columns are partially missing
        user = (row.get("user") or "").strip()
        mode = (row.get("mode") or "").strip()

        # Validate User Identifier existence
        if not user:
            result["valid"] = False
            result["errors"].append(f"Row {row_number}: Missing required user identifier.")
            continue

        # Validate Enrollment Track Mode
        if mode not in ALLOWED_MODES:
            result["valid"] = False
            result["errors"].append(
                f"Row {row_number}: Invalid enrollment mode '{mode}'. Expected one of {ALLOWED_MODES}."
            )

        # Handle user identity duplication
        if user in seen_users:
            result["warnings"].append(f"Row {row_number}: Duplicate user identifier found for '{user}'.")
        
        seen_users.add(user)

        # Sanitize row data spaces for consistent team parsing later
        sanitized_row = {k: (v or "").strip() for k, v in row.items() if k is not None}
        result["rows"].append(sanitized_row)

    # 7. Check if file contains headers but zero actual records
    if not has_rows:
        result["valid"] = False
        result["errors"].append("CSV contains headers but has no student records.")

    return result


def resolve_user_identity(identifier_str: str):
    """
    Phase C4: Multi-stage cascade identity resolution helper.
    Priority Order Evaluation:
      1. student-key (Numeric lookup fallback)
      2. edx-username (Case-insensitive)
      3. edx-email (Case-insensitive)
    
    Returns:
        User instance if located, otherwise None.
    """
    clean_identifier = str(identifier_str).strip()
    if not clean_identifier:
        return None

    # Step 1: Match by student-key (if the identifier is entirely digits/numeric ID)
    if clean_identifier.isdigit():
        try:
            return User.objects.get(id=int(clean_identifier))
        except (User.DoesNotExist, ValueError):
            pass  # Fall through to next identifier check

    # Step 2: Match by edx-username
    try:
        return User.objects.get(username__iexact=clean_identifier)
    except User.DoesNotExist:
        pass  # Fall through to next identifier check

    # Step 3: Match by edx-email
    if "@" in clean_identifier:
        try:
            return User.objects.get(email__iexact=clean_identifier)
        except User.DoesNotExist:
            pass

    # Log unresolved identifiers explicitly to backend error streams
    logger.error(f"Failed to resolve learner identity for string: '{clean_identifier}'")
    return None