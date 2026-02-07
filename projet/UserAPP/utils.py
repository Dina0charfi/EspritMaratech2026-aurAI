def arabic_to_latin(text):
    overrides = {
        "مرأة": "mar2a",
        "امرأة": "mar2a",
        "امراة": "mar2a",
    }
    if text in overrides:
        return overrides[text]

    mapping = {
        "ا":"a","ب":"b","ت":"t","ث":"th","ج":"j","ح":"h","خ":"kh",
        "د":"d","ذ":"dh","ر":"r","ز":"z","س":"s","ش":"sh",
        "ص":"s","ض":"d","ط":"t","ظ":"dh","ع":"aa","غ":"gh",
        "ف":"f","ق":"q","ك":"k","ل":"l","م":"m","ن":"n",
        "ه":"h","و":"w","ي":"i","ة":"a","ّ":"",
        "ء":"2","أ":"2","إ":"2","ؤ":"2","ئ":"2"
    }

    result = ""
    for char in text:
        result += mapping.get(char, char)
    return result


