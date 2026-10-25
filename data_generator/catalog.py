"""Building blocks for realistic UAE SME invoices (all names are invented)."""

EMIRATE_CITIES = {
    "DXB": [("Dubai", "دبي")],
    "AUH": [("Abu Dhabi", "أبوظبي"), ("Al Ain", "العين")],
    "SHJ": [("Sharjah", "الشارقة")],
    "AJM": [("Ajman", "عجمان")],
    "UAQ": [("Umm Al Quwain", "أم القيوين")],
    "RAK": [("Ras Al Khaimah", "رأس الخيمة")],
    "FUJ": [("Fujairah", "الفجيرة")],
}

STREETS = [
    ("Sheikh Zayed Road", "شارع الشيخ زايد"), ("Al Wahda Street", "شارع الوحدة"),
    ("Al Ittihad Road", "شارع الاتحاد"), ("Khalifa Street", "شارع خليفة"),
    ("Al Nuaimiya Street", "شارع النعيمية"), ("Corniche Road", "شارع الكورنيش"),
    ("Al Qusais Industrial Area 4", "القصيص الصناعية 4"), ("Al Jurf Industrial Area", "منطقة الجرف الصناعية"),
    ("Hamdan Street", "شارع حمدان"), ("King Faisal Street", "شارع الملك فيصل"),
    ("Al Barsha 1", "البرشاء 1"), ("Musaffah M-12", "مصفح م-12"), ("Al Majaz 2", "المجاز 2"),
]

# (English stem, Arabic stem)
NAME_STEMS = [
    ("Al Noor", "النور"), ("Gulf Star", "نجمة الخليج"), ("Blue Coast", "الساحل الأزرق"),
    ("Desert Rose", "وردة الصحراء"), ("Al Rayyan", "الريان"), ("Emirates Pearl", "لؤلؤة الإمارات"),
    ("Al Hikma", "الحكمة"), ("Falcon Line", "خط الصقر"), ("Al Safa", "الصفا"), ("Oasis Bright", "واحة الإشراق"),
    ("Al Manara", "المنارة"), ("Silver Dune", "الكثبان الفضية"), ("Al Mustaqbal", "المستقبل"),
    ("Palm Gate", "بوابة النخيل"), ("Al Waha", "الواحة"), ("Golden Sail", "الشراع الذهبي"),
    ("Al Bayan", "البيان"), ("Crescent Bay", "خليج الهلال"), ("Al Fajr", "الفجر"), ("Coral Reef", "الشعاب المرجانية"),
    ("Al Jazeera", "الجزيرة"), ("Sky Tower", "برج السماء"), ("Al Thuraya", "الثريا"), ("Green Leaf", "الورقة الخضراء"),
    ("Al Sahel", "الساحل"), ("Najm Al Sharq", "نجم الشرق"), ("Al Khaleej", "الخليج"), ("Bright Path", "الطريق المشرق"),
]

# (English suffix, Arabic pattern with {} for the stem)
LEGAL_FORMS = [
    ("Trading LLC", "{} للتجارة ذ.م.م"), ("General Trading LLC", "{} للتجارة العامة ذ.م.م"),
    ("Technical Services LLC", "{} للخدمات الفنية ذ.م.م"), ("Building Materials Trading", "{} لتجارة مواد البناء"),
    ("Catering Services", "{} لخدمات التموين"), ("Logistics FZE", "{} للخدمات اللوجستية م.م.ح"),
    ("IT Solutions LLC", "{} لحلول تقنية المعلومات ذ.م.م"), ("Contracting LLC", "مؤسسة {} للمقاولات"),
    ("Office Supplies Trading", "{} لتجارة اللوازم المكتبية"), ("Auto Spare Parts Trading", "{} لتجارة قطع غيار السيارات"),
]

# Goods: (English, Arabic, HS code, unit price range AED, unit code)
GOODS = [
    ("A4 copy paper (box of 5 reams)", "ورق تصوير A4 (كرتون 5 رزم)", "480256", (85, 140), "H87"),
    ("Printer toner cartridge", "خرطوشة حبر طابعة", "844399", (180, 420), "H87"),
    ("Office chair, ergonomic", "كرسي مكتب مريح", "940130", (350, 1200), "H87"),
    ("LED panel light 60x60", "إضاءة ليد 60×60", "940540", (55, 160), "H87"),
    ("Cement bag 50 kg", "كيس إسمنت 50 كغ", "252329", (14, 22), "H87"),
    ("Steel rebar 12 mm (ton)", "حديد تسليح 12 مم (طن)", "721420", (2300, 3100), "TNE"),
    ("PVC pipe 4 inch (6 m)", "أنبوب بي في سي 4 إنش (6 م)", "391723", (38, 75), "H87"),
    ("Paint, emulsion 18 L", "دهان مائي 18 لتر", "320910", (120, 260), "H87"),
    ("Drinking water 500 ml (carton)", "مياه شرب 500 مل (كرتون)", "220110", (9, 16), "H87"),
    ("Basmati rice 25 kg", "أرز بسمتي 25 كغ", "100630", (95, 160), "H87"),
    ("Frozen chicken 10 kg", "دجاج مجمد 10 كغ", "020712", (85, 140), "H87"),
    ("Laptop 14 inch", "حاسوب محمول 14 إنش", "847130", (2200, 4800), "H87"),
    ("Network switch 24-port", "محول شبكة 24 منفذ", "851762", (650, 1900), "H87"),
    ("Brake pads set", "طقم فحمات فرامل", "870830", (120, 380), "H87"),
    ("Engine oil 5W-30 4 L", "زيت محرك 5W-30 4 لتر", "271019", (75, 160), "H87"),
    ("Car battery 70 Ah", "بطارية سيارة 70 أمبير", "850710", (320, 620), "H87"),
    ("Safety helmet", "خوذة سلامة", "650610", (18, 45), "H87"),
    ("Cleaning detergent 5 L", "منظف 5 لتر", "340220", (25, 60), "H87"),
]

# Services: (English, Arabic, service accounting code, price range, unit code)
SERVICES = [
    ("Installation service", "خدمة تركيب", "998732", (150, 450), "HUR"),
    ("AC maintenance visit", "زيارة صيانة مكيفات", "998719", (180, 600), "C62"),
    ("Delivery charges", "رسوم توصيل", "996511", (50, 250), "C62"),
    ("IT support (monthly)", "دعم تقني (شهري)", "998313", (1500, 6000), "MON"),
    ("Catering service per person", "خدمة تموين للشخص", "996334", (35, 120), "C62"),
    ("Cleaning service", "خدمة تنظيف", "998533", (90, 300), "HUR"),
    ("Consultancy", "استشارات", "998311", (400, 1500), "HUR"),
    ("Equipment rental (day)", "تأجير معدات (يوم)", "997313", (250, 1200), "DAY"),
]

PAYMENT_TERMS = [("Net 30", "خلال 30 يوماً"), ("Net 15", "خلال 15 يوماً"), ("Due on receipt", "مستحق عند الاستلام"),
                 ("Net 60", "خلال 60 يوماً")]
BANKS = ["Emirates NBD", "ADCB", "Mashreq", "First Abu Dhabi Bank", "Dubai Islamic Bank", "RAKBANK"]
