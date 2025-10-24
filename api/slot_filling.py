SLOT_REQUIREMENTS = {
    'schedule': ['date_str', 'time_str', 'service'],
    'cancel': ['phone'],
    'confirmation': ['confirmation']
}

def check_required_slots(intent, data):
    missing = []
    for slot in SLOT_REQUIREMENTS.get(intent, []):
        if not data.get(slot):
            missing.append(slot)
    return missing