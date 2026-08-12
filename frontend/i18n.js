/**
 * Aadhaar Health Bridge - Instant Multi-Language i18n Engine
 * Complete Offline-Ready Dictionaries for: English (en), Hindi (hi), Bengali (bn), Tamil (ta), Telugu (te), Marathi (mr)
 */

(function () {
  const SUPPORTED_LANGUAGES = [
    { code: 'en', label: 'EN', native: 'English', full: 'English' },
    { code: 'hi', label: 'हि', native: 'हिन्दी', full: 'Hindi' },
    { code: 'bn', label: 'বাং', native: 'বাংলা', full: 'Bengali' },
    { code: 'ta', label: 'தமி', native: 'தமிழ்', full: 'Tamil' },
    { code: 'te', label: 'తెలు', native: 'తెలుగు', full: 'Telugu' },
    { code: 'mr', label: 'मरा', native: 'मराठी', full: 'Marathi' }
  ];

  let currentLang = localStorage.getItem('hb_lang') || 'en';

  const DICTIONARIES = {
    en: {
      "app.name": "Aadhaar Health Bridge",
      "app.tagline": "Universal Digital Health Vault & AI Clinical Assistant",
      "nav.online": "Online",
      "nav.offline": "Offline Mode",
      "nav.install": "Install App",
      "nav.overview": "Overview & Vitals",
      "nav.biomarkers": "Lab Biomarkers",
      "nav.documents": "Upload Records",
      "nav.files": "Medical Files & Reports",
      "nav.chat": "Local RAG AI",
      "nav.audit": "Audit Trail",
      "nav.emergency": "Emergency QR",
      "nav.logout": "Logout",
      "files.title": "Patient Medical Files & PDF Vault",
      "files.subtitle": "View, preview, and share laboratory reports and prescriptions instantly",
      "files.search_placeholder": "🔍 Search files by name or category...",
      "files.open_pdf": "Open PDF",
      "files.share_whatsapp": "Share on WhatsApp",
      "files.download": "Download",
      "files.empty": "No PDF reports found in this vault. Upload a document to view and share.",
      "files.preview_title": "Medical Report Preview",
      "files.open_new_tab": "Open in New Tab",
      "auth.title": "Access Digital Vault",
      "auth.subtitle": "Authenticate with OAuth 2.0 / Argon2id secured credentials.",
      "auth.username": "Username or ABHA ID",
      "auth.password": "Master Vault Password",
      "auth.signin": "Sign In to Vault",
      "auth.signup": "Create Account",
      "auth.init_vault": "Initialize New Patient Vault",
      "auth.quick_demo": "Quick Demo",
      "vault.active_vault": "Active Vault",
      "vault.add_member_btn": "+ Member",
      "vault.export_fhir": "Export FHIR R4 Bundle",
      "vault.full_name": "Full Name",
      "vault.relation": "Relation",
      "vault.blood_group": "Blood Group",
      "overview.title": "Patient Clinical Profile",
      "overview.subtitle": "HL7 FHIR R4 Compliant Personal Health Record",
      "overview.edit_profile": "Edit Profile & Contacts",
      "overview.emergency_pass": "Emergency Pass",
      "overview.abo_verified": "ABO/Rh Verified",
      "overview.primary_emergency": "Primary Emergency Contact",
      "overview.call_primary": "Call Primary",
      "overview.emergency_readiness": "Emergency Readiness",
      "overview.scans_allowed": "Paramedic QR Scans Allowed",
      "overview.caregiver_contacts_title": "Emergency Caregiver Contacts (At least 2 for Rescue)",
      "overview.manage_contacts": "Manage Contacts",
      "overview.allergies": "Severe Allergies",
      "overview.conditions": "Chronic Conditions",
      "overview.medications": "Active Medications",
      "overview.none_reported": "None reported",
      "overview.emergency_contact": "Emergency Contact",
      "overview.no_phone": "No phone number",
      "overview.no_contacts_warning": "No Caregiver Emergency Contacts Registered",
      "overview.no_contacts_desc": "Add at least 2 emergency contacts so first responders can reach your family during an emergency.",
      "overview.add_contacts_btn": "Add 2 Emergency Contacts",
      "biomarkers.title": "Extracted Clinical Biomarkers",
      "biomarkers.subtitle": "HL7 FHIR Observation Records Extracted from PDF Reports",
      "biomarkers.search_placeholder": "🔍 Search biomarkers (e.g. Glucose)...",
      "biomarkers.empty": "No health metrics extracted yet. Upload a lab report PDF.",
      "documents.title": "Medical Record Ingestion",
      "documents.subtitle": "Secure Zero-Egress Local PDF Parsing & Vector Indexing",
      "documents.drag_drop": "Drag and drop medical PDF reports here",
      "documents.click_browse": "or click to browse from your device",
      "documents.category": "Document Category",
      "documents.upload_btn": "Process & Index Document",
      "documents.uploaded_records": "Uploaded Medical Records",
      "documents.empty": "No medical documents uploaded yet.",
      "chat.title": "Privacy-First AI Clinical Assistant",
      "chat.subtitle": "Runs locally on device with Ollama & Prompt Injection Guardrails",
      "chat.clear": "Clear Chat",
      "chat.welcome_msg": "👋 Hello! I am your Privacy-First Clinical AI Assistant. I analyze your uploaded lab results, discharge summaries, and prescriptions offline with zero cloud egress. How can I help you today?",
      "chat.qp_glucose": "Latest Blood Sugar",
      "chat.qp_summary": "Summarize Lab Results",
      "chat.qp_meds": "Medication Schedule",
      "chat.placeholder": "Ask a clinical question about your records...",
      "chat.send": "Send",
      "audit.title": "HL7 FHIR AuditEvent Trail",
      "audit.subtitle": "Immutable access log verifying HIPAA & ABDM compliance",
      "audit.empty": "No audit logs recorded yet.",
      "emergency.title": "Offline Paramedic Emergency Pass",
      "emergency.subtitle": "Paramedic glass-breaker access for first responders with zero network connectivity",
      "emergency.scan_title": "Scan for Emergency Medical Brief",
      "emergency.scan_subtitle": "Point any phone camera or scanner to decrypt vital triage card",
      "emergency.print_card": "Print Card",
      "emergency.test_offline": "Test Offline View",
      "emergency.triage_included": "Triage Information Included",
      "emergency.triage_blood": "Blood Group & ABO Compatibility",
      "emergency.triage_allergies": "Critical Allergies & Anaphylaxis Warnings",
      "emergency.triage_conditions": "Chronic Conditions & Active Prescriptions",
      "emergency.triage_call": "1-Touch Emergency Caregiver Call Bridge",
      "emergency.triage_crypto": "Zero-Knowledge Client-Side AES Decryption",
      "modal.add_member_title": "Add Family Member Vault",
      "modal.edit_profile_title": "Edit Profile & Emergency Contacts",
      "modal.edit_profile_subtitle": "Configure vital medical info and at least 2 emergency caregiver contacts",
      "modal.cancel": "Cancel",
      "modal.save_profile": "Save Profile & Update Pass",
      "modal.create_vault": "Create Vault",
      "offline.title": "Offline Medical Card",
      "offline.subtitle": "Secure Local Device Caching Active",
      "offline.emergency_badge": "Emergency",
      "offline.patient_name": "Patient Name",
      "offline.blood_group": "Blood Group",
      "offline.allergies": "Severe Allergies",
      "offline.conditions": "Chronic Medical Conditions",
      "offline.medications": "Active Medications",
      "offline.caregiver_contacts": "Caregiver Emergency Contacts",
      "offline.emergency_card_link": "Emergency Card Link",
      "contact.primary": "Primary Contact",
      "contact.secondary": "Secondary Contact",
      "contact.alternative": "Alternative",
      "contact.call": "Call",
      "contact.caregiver": "Caregiver",
      "rel.self": "Self",
      "rel.father": "Father",
      "rel.mother": "Mother",
      "rel.spouse": "Spouse",
      "rel.child": "Child",
      "rel.parent": "Parent",
      "rel.sibling": "Sibling",
      "rel.friend": "Friend",
      "rel.other": "Other",
      "status.active": "Active",
      "status.disabled": "Disabled"
    },
    hi: {
      "app.name": "आधार हेल्थ ब्रिज",
      "app.tagline": "सार्वभौमिक डिजिटल स्वास्थ्य वॉल्ट एवं एआई नैदानिक सहायक",
      "nav.online": "ऑनलाइन",
      "nav.offline": "ऑफ़लाइन मोड",
      "nav.install": "ऐप इंस्टॉल करें",
      "nav.overview": "अवलोकन एवं महत्वपूर्ण संकेत",
      "nav.biomarkers": "लैब बायोमार्कर",
      "nav.documents": "दस्तावेज अपलोड",
      "nav.files": "चिकित्सा फ़ाइलें एवं रिपोर्ट",
      "nav.chat": "लोकल RAG एआई",
      "nav.audit": "ऑडिट ट्रेल",
      "nav.emergency": "आपातकालीन क्यूआर",
      "nav.logout": "लॉग-आउट",
      "files.title": "रोगी चिकित्सा फ़ाइलें एवं पीडीएफ वॉल्ट",
      "files.subtitle": "लैब रिपोर्ट और नुस्खे तुरंत देखें, पूर्वावलोकन करें और साझा करें",
      "files.search_placeholder": "🔍 नाम या श्रेणी के अनुसार फ़ाइलें खोजें...",
      "files.open_pdf": "पीडीएफ खोलें",
      "files.share_whatsapp": "व्हाट्सएप पर साझा करें",
      "files.download": "डाउनलोड",
      "files.empty": "इस वॉल्ट में कोई पीडीएफ रिपोर्ट नहीं मिली। देखने और साझा करने के लिए दस्तावेज अपलोड करें।",
      "files.preview_title": "चिकित्सा रिपोर्ट पूर्वावलोकन",
      "files.open_new_tab": "नए टैब में खोलें",
      "auth.title": "डिजिटल वॉल्ट में प्रवेश करें",
      "auth.subtitle": "OAuth 2.0 / Argon2id सुरक्षित क्रेडेंशियल्स के साथ प्रमाणित करें।",
      "auth.username": "उपयोगकर्ता नाम या आभा आईडी",
      "auth.password": "मास्टर वॉल्ट पासवर्ड",
      "auth.signin": "वॉल्ट में साइन इन करें",
      "auth.signup": "नया खाता बनाएं",
      "auth.init_vault": "नया रोगी वॉल्ट प्रारंभ करें",
      "auth.quick_demo": "त्वरित डेमो",
      "vault.active_vault": "सक्रिय वॉल्ट",
      "vault.add_member_btn": "+ सदस्य जोड़ें",
      "vault.export_fhir": "FHIR R4 बंडल निर्यात करें",
      "vault.full_name": "पूरा नाम",
      "vault.relation": "संबंध",
      "vault.blood_group": "रक्त समूह",
      "overview.title": "रोगी नैदानिक प्रोफाइल",
      "overview.subtitle": "HL7 FHIR R4 अनुरूप व्यक्तिगत स्वास्थ्य रिकॉर्ड",
      "overview.edit_profile": "प्रोफाइल एवं संपर्क संपादित करें",
      "overview.emergency_pass": "आपातकालीन पास",
      "overview.abo_verified": "ABO/Rh सत्यापित",
      "overview.primary_emergency": "प्राथमिक आपातकालीन संपर्क",
      "overview.call_primary": "प्राथमिक को कॉल करें",
      "overview.emergency_readiness": "आपातकालीन तत्परता",
      "overview.scans_allowed": "पैरामेडिक क्यूआर स्कैन की अनुमति है",
      "overview.caregiver_contacts_title": "आपातकालीन देखभालकर्ता संपर्क (बचाव के लिए कम से कम 2)",
      "overview.manage_contacts": "संपर्क प्रबंधित करें",
      "overview.allergies": "गंभीर एलर्जी",
      "overview.conditions": "पुरानी बीमारियां",
      "overview.medications": "सक्रिय दवाएं",
      "overview.none_reported": "कोई दर्ज नहीं",
      "overview.emergency_contact": "आपातकालीन संपर्क",
      "overview.no_phone": "कोई फोन नंबर नहीं",
      "overview.no_contacts_warning": "कोई देखभालकर्ता संपर्क पंजीकृत नहीं है",
      "overview.no_contacts_desc": "कम से कम 2 आपातकालीन संपर्क जोड़ें ताकि आपात स्थिति में प्रथम उत्तरदाता आपके परिवार तक पहुंच सकें।",
      "overview.add_contacts_btn": "2 आपातकालीन संपर्क जोड़ें",
      "biomarkers.title": "निकाले गए नैदानिक बायोमार्कर",
      "biomarkers.subtitle": "पीडीएफ रिपोर्ट से निकाले गए HL7 FHIR अवलोकन रिकॉर्ड",
      "biomarkers.search_placeholder": "🔍 बायोमार्कर खोजें (जैसे: ग्लूकोज)...",
      "biomarkers.empty": "अभी तक कोई स्वास्थ्य मीट्रिक नहीं निकाली गई है। लैब रिपोर्ट पीडीएफ अपलोड करें।",
      "documents.title": "चिकित्सा दस्तावेज अंतर्ग्रहण",
      "documents.subtitle": "सुरक्षित स्थानीय पीडीएफ पार्सिंग एवं वेक्टर इंडेक्सिंग",
      "documents.drag_drop": "चिकित्सा रिपोर्ट पीडीएफ यहाँ खींचें और छोड़ें",
      "documents.click_browse": "या अपने डिवाइस से ब्राउज़ करने के लिए क्लिक करें",
      "documents.category": "दस्तावेज श्रेणी",
      "documents.upload_btn": "दस्तावेज प्रोसेस एवं इंडेक्स करें",
      "documents.uploaded_records": "अपलोड किए गए चिकित्सा रिकॉर्ड",
      "documents.empty": "अभी तक कोई चिकित्सा दस्तावेज अपलोड नहीं किया गया है।",
      "chat.title": "गोपनीयता-प्रथम एआई नैदानिक सहायक",
      "chat.subtitle": "ओलामा और प्रॉम्प्ट इंजेक्शन सुरक्षा के साथ डिवाइस पर स्थानीय रूप से चलता है",
      "chat.clear": "चैट साफ़ करें",
      "chat.welcome_msg": "नमस्ते! मैं आपका गोपनीयता-प्रथम नैदानिक एआई सहायक हूँ। मैं आपकी अपलोड की गई रिपोर्ट और दवाओं का विश्लेषण करता हूँ। आज मैं आपकी क्या मदद कर सकता हूँ?",
      "chat.qp_glucose": "नवीनतम ब्लड शुगर",
      "chat.qp_summary": "लैब परिणामों का सारांश",
      "chat.qp_meds": "दवा अनुसूची",
      "chat.placeholder": "अपने रिकॉर्ड के बारे में नैदानिक प्रश्न पूछें...",
      "chat.send": "भेजें",
      "audit.title": "HL7 FHIR AuditEvent ऑडिट लॉग ट्रेल",
      "audit.subtitle": "HIPAA और ABDM अनुपालन सत्यापित करने वाला अपरिवर्तनीय एक्सेस लॉग",
      "audit.empty": "अभी तक कोई ऑडिट लॉग दर्ज नहीं हुआ है।",
      "emergency.title": "ऑफ़लाइन पैरामेडिक आपातकालीन पास",
      "emergency.subtitle": "बिना इंटरनेट कनेक्टिविटी के प्रथम उत्तरदाताओं के लिए ग्लास-ब्रेकर एक्सेस",
      "emergency.scan_title": "आपातकालीन चिकित्सा विवरण के लिए स्कैन करें",
      "emergency.scan_subtitle": "महत्वपूर्ण ट्राइएज कार्ड डिक्रिप्ट करने के लिए किसी भी फोन से स्कैन करें",
      "emergency.print_card": "कार्ड प्रिंट करें",
      "emergency.test_offline": "ऑफ़लाइन दृश्य परीक्षण करें",
      "emergency.triage_included": "शामिल ट्राइएज जानकारी",
      "emergency.triage_blood": "रक्त समूह एवं ABO अनुकूलता",
      "emergency.triage_allergies": "महत्वपूर्ण एलर्जी और चेतावनी",
      "emergency.triage_conditions": "पुरानी स्थितियां एवं सक्रिय नुस्खे",
      "emergency.triage_call": "1-टच आपातकालीन देखभालकर्ता कॉल ब्रिज",
      "emergency.triage_crypto": "शून्य-ज्ञान क्लाइंट-साइड एईएस डिक्रिप्शन",
      "modal.add_member_title": "परिवार के सदस्य का वॉल्ट जोड़ें",
      "modal.edit_profile_title": "प्रोफाइल एवं आपातकालीन संपर्क संपादित करें",
      "modal.edit_profile_subtitle": "महत्वपूर्ण चिकित्सा जानकारी और कम से कम 2 देखभालकर्ता संपर्क कॉन्फ़िगर करें",
      "modal.cancel": "रद्द करें",
      "modal.save_profile": "प्रोफाइल सहेजें एवं पास अपडेट करें",
      "modal.create_vault": "वॉल्ट बनाएं",
      "offline.title": "ऑफ़लाइन मेडिकल कार्ड",
      "offline.subtitle": "सुरक्षित स्थानीय उपकरण कैशिंग सक्रिय",
      "offline.emergency_badge": "आपातकालीन",
      "offline.patient_name": "रोगी का नाम",
      "offline.blood_group": "रक्त समूह",
      "offline.allergies": "गंभीर एलर्जी",
      "offline.conditions": "पुरानी चिकित्सीय स्थितियां",
      "offline.medications": "सक्रिय दवाएं",
      "offline.caregiver_contacts": "देखभालकर्ता आपातकालीन संपर्क",
      "offline.emergency_card_link": "आपातकालीन कार्ड लिंक",
      "contact.primary": "प्राथमिक संपर्क",
      "contact.secondary": "द्वितीयक संपर्क",
      "contact.alternative": "वैकल्पिक संपर्क",
      "contact.call": "कॉल करें",
      "contact.caregiver": "देखभालकर्ता",
      "rel.self": "स्वयं",
      "rel.father": "पिता",
      "rel.mother": "माता",
      "rel.spouse": "जीवनसाथी",
      "rel.child": "बच्चा",
      "rel.parent": "अभिभावक",
      "rel.sibling": "भाई/बहन",
      "rel.friend": "मित्र",
      "rel.other": "अन्य",
      "status.active": "सक्रिय",
      "status.disabled": "निष्क्रिय"
    },
    bn: {
      "app.name": "আধার হেলথ ব্রিজ",
      "app.tagline": "সর্বজনীন ডিজিটাল স্বাস্থ্য ভল্ট এবং এআই ক্লিনিকাল সহকারী",
      "nav.online": "অনলাইন",
      "nav.offline": "অফলাইন মোড",
      "nav.install": "অ্যাপ ইনস্টল করুন",
      "nav.overview": "ওভারভিউ এবং গুরুত্বপূর্ণ লক্ষণ",
      "nav.biomarkers": "ল্যাব বায়োমার্কার",
      "nav.documents": "চিকিৎসা সংক্রান্ত নথি",
      "nav.chat": "লোকাল RAG এআই",
      "nav.audit": "অডিট ট্রেইল",
      "nav.emergency": "জরুরী কিউআর",
      "nav.logout": "লগ আউট",
      "auth.title": "ডিজিটাল ভল্ট খুলুন",
      "auth.subtitle": "OAuth 2.0 / Argon2id সুরক্ষিত শংসাপত্র দিয়ে প্রমাণীকরণ করুন।",
      "auth.username": "ব্যবহারকারীর নাম বা আভা আইডি",
      "auth.password": "মাস্টার ভল্ট পাসওয়ার্ড",
      "auth.signin": "ভল্টে সাইন ইন করুন",
      "auth.signup": "নতুন অ্যাকাউন্ট তৈরি করুন",
      "auth.init_vault": "নতুন রোগীর ভল্ট শুরু করুন",
      "auth.quick_demo": "দ্রুত ডেমো",
      "vault.active_vault": "সক্রিয় ভল্ট",
      "vault.add_member_btn": "+ সদস্য যোগ করুন",
      "vault.export_fhir": "FHIR R4 বান্ডিল এক্সপোর্ট করুন",
      "vault.full_name": "পুরো নাম",
      "vault.relation": "সম্পর্ক",
      "vault.blood_group": "রক্তের গ্রুপ",
      "overview.title": "রোগীর ক্লিনিকাল প্রোফাইল",
      "overview.subtitle": "HL7 FHIR R4 সম্মত ব্যক্তিগত স্বাস্থ্য রেকর্ড",
      "overview.edit_profile": "প্রোফাইল ও যোগাযোগ সম্পাদনা",
      "overview.emergency_pass": "জরুরী পাস",
      "overview.abo_verified": "ABO/Rh যাচাইকৃত",
      "overview.primary_emergency": "প্রাথমিক জরুরী যোগাযোগ",
      "overview.call_primary": "প্রাথমিকে কল করুন",
      "overview.emergency_readiness": "জরুরী প্রস্তুতি",
      "overview.scans_allowed": "প্যারামেডিক কিউআর স্ক্যান অনুমোদিত",
      "overview.caregiver_contacts_title": "জরুরী কেয়ারগিভার পরিচিতি (উদ্ধারের জন্য কমপক্ষে ২টি)",
      "overview.manage_contacts": "যোগাযোগ পরিচালনা করুন",
      "overview.allergies": "মারাত্মক অ্যালার্জি",
      "overview.conditions": "দীর্ঘস্থায়ী রোগ",
      "overview.medications": "চলতি ওষুধ",
      "overview.none_reported": "কিছু নথিভুক্ত নেই",
      "overview.emergency_contact": "জরুরী যোগাযোগ",
      "overview.no_phone": "কোন ফোন নম্বর নেই",
      "overview.no_contacts_warning": "কোন কেয়ারগিভার যোগাযোগ নিবন্ধিত নেই",
      "overview.no_contacts_desc": "কমপক্ষে ২টি জরুরী যোগাযোগ যোগ করুন যাতে উদ্ধারকারীরা আপনার পরিবারের কাছে পৌঁছাতে পারে।",
      "overview.add_contacts_btn": "২টি জরুরী যোগাযোগ যোগ করুন",
      "biomarkers.title": "নিষ্কাশিত ক্লিনিকাল বায়োমার্কার",
      "biomarkers.subtitle": "পিডিএফ রিপোর্ট থেকে সংগৃহীত HL7 FHIR পর্যবেক্ষণ রেকর্ড",
      "biomarkers.search_placeholder": "🔍 বায়োমার্কার খুঁজুন (যেমন: গ্লুকোজ)...",
      "biomarkers.empty": "এখনও কোনও স্বাস্থ্য মেট্রিক নিষ্কাশন করা হয়নি। একটি ল্যাব রিপোর্ট পিডিএফ আপলোড করুন।",
      "documents.title": "চিকিৎসা সংক্রান্ত নথি গ্রহণ",
      "documents.subtitle": "নিরাপদ জিরো-ইগ্রেস লোকাল পিডিএফ বিশ্লেষণ ও ভেক্টর ইনডেক্সিং",
      "documents.drag_drop": "চিকিৎসা সংক্রান্ত রিপোর্ট পিডিএফ এখানে ড্র্যাগ এবং ড্রপ করুন",
      "documents.click_browse": "অথবা আপনার ডিভাইস থেকে ব্রাউজ করতে ক্লিক করুন",
      "documents.category": "নথির বিভাগ",
      "documents.upload_btn": "নথি প্রক্রিয়া ও ইনডেক্স করুন",
      "documents.uploaded_records": "আপলোড করা চিকিৎসা রেকর্ড",
      "documents.empty": "এখনও কোনও চিকিৎসা সংক্রান্ত নথি আপলোড করা হয়নি।",
      "chat.title": "গোপনীয়তা-প্রথম এআই ক্লিনিকাল সহকারী",
      "chat.subtitle": "ওলামা এবং প্রম্পট ইনজেকশন সুরক্ষার সাথে ডিভাইসে স্থানীয়ভাবে চলে",
      "chat.clear": "চ্যাট মুছে ফেলুন",
      "chat.welcome_msg": "হ্যালো! আমি আপনার গোপনীয়তা-প্রথম ক্লিনিকাল এআই সহকারী। আমি আপনার আপলোড করা রিপোর্ট এবং ওষুধ বিশ্লেষণ করি। আজ আপনাকে কীভাবে সাহায্য করতে পারি?",
      "chat.qp_glucose": "সর্বশেষ রক্তের শর্করা",
      "chat.qp_summary": "ল্যাব ফলাফলের সারাংশ",
      "chat.qp_meds": "ওষুধের সময়সূচী",
      "chat.placeholder": "আপনার রেকর্ড সম্পর্কে ক্লিনিকাল প্রশ্ন জিজ্ঞাসা করুন...",
      "chat.send": "পাঠান",
      "audit.title": "HL7 FHIR AuditEvent অডিট লগ ট্রেইল",
      "audit.subtitle": "HIPAA এবং ABDM সম্মতি যাচাইকারী অপরিবর্তনীয় অ্যাক্সেস লগ",
      "audit.empty": "এখনও কোনও অডিট লগ রেকর্ড করা হয়নি।",
      "emergency.title": "অফলাইন প্যারামেডিক জরুরী পাস",
      "emergency.subtitle": "ইন্টারনেট সংযোগ ছাড়াই প্রাথমিক প্রতিক্রিয়াকারীদের জন্য গ্লাস-ব্রেকার অ্যাক্সেস",
      "emergency.scan_title": "জরুরী চিকিৎসা বিবরণের জন্য স্ক্যান করুন",
      "emergency.scan_subtitle": "গুরুত্বপূর্ণ ট্রায়াজ কার্ড ডিক্রিপ্ট করতে যেকোনো ফোন থেকে স্ক্যান করুন",
      "emergency.print_card": "কার্ড প্রিন্ট করুন",
      "emergency.test_offline": "অফলাইন ভিউ পরীক্ষা করুন",
      "emergency.triage_included": "অন্তর্ভুক্ত ট্রায়াজ তথ্য",
      "emergency.triage_blood": "রক্তের গ্রুপ ও ABO সামঞ্জস্যতা",
      "emergency.triage_allergies": "মারাত্মক অ্যালার্জি ও সতর্কবার্তা",
      "emergency.triage_conditions": "দীর্ঘস্থায়ী অবস্থা ও সক্রিয় প্রেসক্রিপশন",
      "emergency.triage_call": "১-টাচ জরুরী কেয়ারগিভার কল ব্রিজ",
      "emergency.triage_crypto": "জিরো-নলেজ ক্লায়েন্ট-সাইড AES ডিক্রিপশন",
      "modal.add_member_title": "পরিবারের সদস্যের ভল্ট যোগ করুন",
      "modal.edit_profile_title": "প্রোফাইল ও জরুরী যোগাযোগ সম্পাদনা করুন",
      "modal.edit_profile_subtitle": "গুরুত্বপূর্ণ চিকিৎসা তথ্য এবং কমপক্ষে ২টি কেয়ারগিভার যোগাযোগ কনফিগার করুন",
      "modal.cancel": "বাতিল করুন",
      "modal.save_profile": "প্রোফাইল সংরক্ষণ ও পাস আপডেট করুন",
      "modal.create_vault": "ভল্ট তৈরি করুন",
      "offline.title": "অফলাইন মেডিকেল কার্ড",
      "offline.subtitle": "নিরাপদ স্থানীয় ডিভাইস ক্যাশিং সক্রিয়",
      "offline.emergency_badge": "জরুরী",
      "offline.patient_name": "রোগীর নাম",
      "offline.blood_group": "রক্তের গ্রুপ",
      "offline.allergies": "মারাত্মক অ্যালার্জি",
      "offline.conditions": "দীর্ঘস্থায়ী রোগ",
      "offline.medications": "চলতি ওষুধ",
      "offline.caregiver_contacts": "কেয়ারগিভার জরুরী যোগাযোগ",
      "offline.emergency_card_link": "জরুরী কার্ড লিংক",
      "contact.primary": "প্রাথমিক যোগাযোগ",
      "contact.secondary": "দ্বিতীয় যোগাযোগ",
      "contact.alternative": "বিকল্প যোগাযোগ",
      "contact.call": "কল করুন",
      "contact.caregiver": "কেয়ারগিভার",
      "rel.self": "নিজে",
      "rel.father": "বাবা",
      "rel.mother": "মা",
      "rel.spouse": "স্বামী/স্ত্রী",
      "rel.child": "সন্তান",
      "rel.parent": "পিতা-মাতা",
      "rel.sibling": "ভাই/বোন",
      "rel.friend": "বন্ধু",
      "rel.other": "অন্যান্য",
      "status.active": "সক্রিয়",
      "status.disabled": "নিষ্ক্রিয়"
    },
    ta: {
      "app.name": "ஆதார் ஹெல்த் பிரிட்ஜ்",
      "app.tagline": "டிஜிட்டல் சுகாதார பெட்டகம் மற்றும் AI மருத்துவ உதவியாளர்",
      "nav.online": "ஆன்லைன்",
      "nav.offline": "ஆஃப்லைன் முறை",
      "nav.install": "செயலியை நிறுவு",
      "nav.overview": "கண்ணோட்டம் & முக்கிய அறிகுறிகள்",
      "nav.biomarkers": "ஆய்வக பயோமார்க்ஸ்",
      "nav.documents": "மருத்துவ ஆவணங்கள்",
      "nav.chat": "உள்ளூர் RAG AI",
      "nav.audit": "தணிக்கை பதிவு",
      "nav.emergency": "அவசர QR",
      "nav.logout": "வெளியேறு",
      "auth.title": "டிஜிட்டல் பெட்டகத்தை அணுகவும்",
      "auth.subtitle": "OAuth 2.0 / Argon2id பாதுகாப்பான சான்றுகளுடன் அங்கீகரிக்கவும்.",
      "auth.username": "பயனர் பெயர் அல்லது ABHA ID",
      "auth.password": "முதன்மை கடவுச்சொல்",
      "auth.signin": "உள்நுழையவும்",
      "auth.signup": "புதிய கணக்கு உருவாக்கு",
      "auth.init_vault": "புதிய நோயாளி பெட்டகத்தை துவங்கு",
      "auth.quick_demo": "விரைவு டெமோ",
      "vault.active_vault": "செயலில் உள்ள பெட்டகம்",
      "vault.add_member_btn": "+ உறுப்பினர் சேர்",
      "vault.export_fhir": "FHIR R4 ஏற்றுமதி செய்",
      "vault.full_name": "முழு பெயர்",
      "vault.relation": "உறவு",
      "vault.blood_group": "இரத்த பிரிவு",
      "overview.title": "நோயாளி மருத்துவ விவரம்",
      "overview.subtitle": "HL7 FHIR R4 இணக்கமான தனிநபர் சுகாதார பதிவு",
      "overview.edit_profile": "சுயவிவரம் & தொடர்புகளை திருத்து",
      "overview.emergency_pass": "அவசர பாஸ்",
      "overview.abo_verified": "ABO/Rh சரிபார்க்கப்பட்டது",
      "overview.primary_emergency": "முதன்மை அவசர தொடர்பு",
      "overview.call_primary": "முதன்மைக்கு அழைக்கவும்",
      "overview.emergency_readiness": "அவசர தயார்நிலை",
      "overview.scans_allowed": "மருத்துவ அவசர QR ஸ்கேன் அனுமதிக்கப்பட்டது",
      "overview.caregiver_contacts_title": "அவசர பராமரிப்பாளர் தொடர்புகள் (குறைந்தது 2 தேவை)",
      "overview.manage_contacts": "தொடர்புகளை நிர்வகி",
      "overview.allergies": "கடுமையான ஒவ்வாமை",
      "overview.conditions": "நாள்பட்ட நோய்கள்",
      "overview.medications": "தற்போதைய மருந்துகள்",
      "overview.none_reported": "எதுவும் பதிவு செய்யப்படவில்லை",
      "overview.emergency_contact": "அவசர தொடர்பு",
      "overview.no_phone": "தொலைபேசி எண் இல்லை",
      "overview.no_contacts_warning": "பராமரிப்பாளர் தொடர்பு பதிவு செய்யப்படவில்லை",
      "overview.no_contacts_desc": "முதலுதவி குழு உங்கள் குடும்பத்தை தொடர்பு கொள்ள குறைந்தது 2 அவசர தொடர்புகளை சேர்க்கவும்.",
      "overview.add_contacts_btn": "2 அவசர தொடர்புகளை சேர்",
      "biomarkers.title": "பிரித்தெடுக்கப்பட்ட பயோமார்க்ஸ்",
      "biomarkers.subtitle": "PDF அறிக்கையிலிருந்து பெறப்பட்ட HL7 FHIR அவதானிப்புகள்",
      "biomarkers.search_placeholder": "🔍 பயோமார்க்ஸ் தேடுங்கள் (எ.கா. குளுக்கோஸ்)...",
      "biomarkers.empty": "இன்னும் சுகாதார அளவீடுகள் இல்லை. PDF பதிவேற்றவும்.",
      "documents.title": "மருத்துவ ஆவண பதிவேற்றம்",
      "documents.subtitle": "பாதுகாப்பான உள்ளூர் PDF பகுப்பாய்வு",
      "documents.drag_drop": "மருத்துவ அறிக்கைகளை இங்கே இழுத்து விடவும்",
      "documents.click_browse": "அல்லது உலாவ கிளிக் செய்யவும்",
      "documents.category": "ஆவண வகை",
      "documents.upload_btn": "ஆவணத்தை செயலாக்கு & அட்டவணைப்படுத்து",
      "documents.uploaded_records": "பதிவேற்றப்பட்ட மருத்துவ ஆவணங்கள்",
      "documents.empty": "இன்னும் ஆவணங்கள் பதிவேற்றப்படவில்லை.",
      "chat.title": "AI மருத்துவ உதவியாளர்",
      "chat.subtitle": "சாதனத்திலேயே இயங்கும் உள்ளூர் AI உதவியாளர்",
      "chat.clear": "அரட்டையை அழிக்கவும்",
      "chat.welcome_msg": "வணக்கம்! நான் உங்கள் AI மருத்துவ உதவியாளர். உங்கள் ஆய்வக அறிக்கைகள் மற்றும் மருந்துகள் குறித்து என்னிடம் கேளுங்கள்.",
      "chat.qp_glucose": "சமீபத்திய இரத்த சர்க்கரை",
      "chat.qp_summary": "ஆய்வக முடிவுகளின் சுருக்கம்",
      "chat.qp_meds": "மருந்து அட்டவணை",
      "chat.placeholder": "உங்கள் பதிவுகள் பற்றி மருத்துவ கேள்வி கேளுங்கள்...",
      "chat.send": "அனுப்பு",
      "audit.title": "HL7 FHIR தணிக்கை பதிவு",
      "audit.subtitle": "HIPAA & ABDM இணக்க பதிவு",
      "audit.empty": "இன்னும் தணிக்கை பதிவுகள் இல்லை.",
      "emergency.title": "ஆஃப்லைன் அவசர பாஸ்",
      "emergency.subtitle": "இணையம் இல்லாத சூழலிலும் முதலுதவிக்கான விரைவு அணுகல்",
      "emergency.scan_title": "அவசர மருத்துவ சுருக்கத்திற்கு ஸ்கேன் செய்யவும்",
      "emergency.scan_subtitle": "ட்ரியேஜ் அட்டையை படிக்க எந்த போனிலும் ஸ்கேன் செய்யலாம்",
      "emergency.print_card": "அட்டையை அச்சிடுக",
      "emergency.test_offline": "ஆஃப்லைன் காட்சியை சோதிக்கவும்",
      "emergency.triage_included": "உள்ளடக்கப்பட்ட தகவல்கள்",
      "emergency.triage_blood": "இரத்த பிரிவு & ABO பொருத்தம்",
      "emergency.triage_allergies": "கடுமையான ஒவ்வாமை எச்சரிக்கைகள்",
      "emergency.triage_conditions": "நாள்பட்ட நோய்கள் & மருந்துகள்",
      "emergency.triage_call": "1-டச் அவசர பராமரிப்பாளர் அழைப்பு",
      "emergency.triage_crypto": "AES குறியாக்க பாதுகாப்பு",
      "modal.add_member_title": "குடும்ப உறுப்பினர் பெட்டகத்தை சேர்",
      "modal.edit_profile_title": "சுயவிவரம் & அவசர தொடர்புகளை திருத்து",
      "modal.edit_profile_subtitle": "முக்கிய மருத்துவ தகவல் மற்றும் குறைந்தது 2 பராமரிப்பாளர் தொடர்புகளை உள்ளிடுக",
      "modal.cancel": "ரத்துசெய்",
      "modal.save_profile": "சுயவிவரத்தை சேமி",
      "modal.create_vault": "பெட்டகத்தை உருவாக்கு",
      "offline.title": "ஆஃப்லைன் மருத்துவ அட்டை",
      "offline.subtitle": "உள்ளூர் சாதனத்தில் பாதுகாப்பாக சேமிக்கப்பட்டுள்ளது",
      "offline.emergency_badge": "அவசரம்",
      "offline.patient_name": "நோயாளி பெயர்",
      "offline.blood_group": "இரத்த பிரிவு",
      "offline.allergies": "கடுமையான ஒவ்வாமை",
      "offline.conditions": "நாள்பட்ட நோய்கள்",
      "offline.medications": "தற்போதைய மருந்துகள்",
      "offline.caregiver_contacts": "பராமரிப்பாளர் அவசர தொடர்புகள்",
      "offline.emergency_card_link": "அவசர அட்டை இணைப்பு",
      "contact.primary": "முதன்மை தொடர்பு",
      "contact.secondary": "இரண்டாம் நிலை தொடர்பு",
      "contact.alternative": "மாற்று தொடர்பு",
      "contact.call": "அழைக்கவும்",
      "contact.caregiver": "பராமரிப்பாளர்",
      "rel.self": "சுய",
      "rel.father": "தந்தை",
      "rel.mother": "தாய்",
      "rel.spouse": "துணைவர்",
      "rel.child": "குழந்தை",
      "rel.parent": "பெற்றோர்",
      "rel.sibling": "உடன்பிறப்பு",
      "rel.friend": "நண்பர்",
      "rel.other": "மற்றவை",
      "status.active": "செயலில்",
      "status.disabled": "முடக்கப்பட்டது"
    },
    te: {
      "app.name": "ఆధార్ హెల్త్ బ్రిడ్జ్",
      "app.tagline": "సార్వత్రిక డిజిటల్ హెల్త్ వాల్ట్ & AI క్లినికల్ అసిస్టెంట్",
      "nav.online": "ఆన్‌లైన్",
      "nav.offline": "ఆఫ్‌లైన్ మోడ్",
      "nav.install": "యాప్ ఇన్‌స్టాల్ చేయండి",
      "nav.overview": "సమీక్ష & ముఖ్య సంకేతాలు",
      "nav.biomarkers": "ల్యాబ్ బయోమార్కర్లు",
      "nav.documents": "వైద్య పత్రాలు",
      "nav.chat": "లోకల్ RAG AI",
      "nav.audit": "ఆడిట్ లాగ్స్",
      "nav.emergency": "ఎమర్జెన్సీ QR",
      "nav.logout": "లాగౌట్",
      "auth.title": "డిజిటల్ వాల్ట్ తెరవండి",
      "auth.subtitle": "OAuth 2.0 / Argon2id సురక్షిత ఆధారాలతో ప్రామాణీకరించండి.",
      "auth.username": "వినియోగదారు పేరు లేదా ABHA ID",
      "auth.password": "మాస్టర్ వాల్ట్ పాస్‌వర్డ్",
      "auth.signin": "వాల్ట్‌లోకి లాగిన్ అవ్వండి",
      "auth.signup": "కొత్త ఖాతా సృష్టించండి",
      "auth.init_vault": "కొత్త పేషెంట్ వాల్ట్ ప్రారంభించండి",
      "auth.quick_demo": "త్వరిత డెమో",
      "vault.active_vault": "యాక్టివ్ వాల్ట్",
      "vault.add_member_btn": "+ సభ్యుడిని చేర్చండి",
      "vault.export_fhir": "FHIR R4 ఎగుమతి చేయండి",
      "vault.full_name": "పూర్తి పేరు",
      "vault.relation": "సంబంధం",
      "vault.blood_group": "రక్త సమూహం",
      "overview.title": "రోగి క్లినికల్ ప్రొఫైల్",
      "overview.subtitle": "HL7 FHIR R4 వ్యక్తిగత ఆరోగ్య రికార్డు",
      "overview.edit_profile": "ప్రొఫైల్ & పరిచయాలను సవరించండి",
      "overview.emergency_pass": "ఎమర్జెన్సీ పాస్",
      "overview.abo_verified": "ABO/Rh ధృవీకరించబడింది",
      "overview.primary_emergency": "ప్రాథమిక ఎమర్జెన్సీ పరిచయం",
      "overview.call_primary": "ప్రాథమికకు కాల్ చేయండి",
      "overview.emergency_readiness": "ఎమర్జెన్సీ సంసిద్ధత",
      "overview.scans_allowed": "పారామెడిక్ QR స్కాన్‌లు అనుమతించబడ్డాయి",
      "overview.caregiver_contacts_title": "ఎమర్జెన్సీ సంరక్షకుల పరిచయాలు (కనీసం 2 అవసరం)",
      "overview.manage_contacts": "పరిచయాలను నిర్వహించండి",
      "overview.allergies": "తీవ్రమైన అలెర్జీలు",
      "overview.conditions": "దీర్ఘకాలిక సమస్యలు",
      "overview.medications": "ప్రస్తుత మందులు",
      "overview.none_reported": "ఏమీ నమోదు కాలేదు",
      "overview.emergency_contact": "ఎమర్జెన్సీ పరిచయం",
      "overview.no_phone": "ఫోన్ నంబర్ లేదు",
      "overview.no_contacts_warning": "సంరక్షకుల పరిచయం నమోదు కాలేదు",
      "overview.no_contacts_desc": "అత్యవసర సమయంలో సహాయకులు మీ కుటుంబాన్ని సంప్రదించడానికి కనీసం 2 పరిచయాలను నమోదు చేయండి.",
      "overview.add_contacts_btn": "2 ఎమర్జెన్సీ పరిచయాలను చేర్చండి",
      "biomarkers.title": "సేకరించిన క్లినికల్ బయోమార్కర్లు",
      "biomarkers.subtitle": "PDF నివేదికల నుండి HL7 FHIR పరిశీలనలు",
      "biomarkers.search_placeholder": "🔍 బయోమార్కర్లను శోధించండి (ఉదా. గ్లూకోజ్)...",
      "biomarkers.empty": "ఇంకా ఆరోగ్య కొలతలు లేవు. ల్యాబ్ రిపోర్ట్ PDF ని అప్‌లోడ్ చేయండి.",
      "documents.title": "వైద్య పత్రాల స్వీకరణ",
      "documents.subtitle": "సురక్షిత లోకల్ PDF విశ్లేషణ",
      "documents.drag_drop": "వైద్య నివేదికల PDF ని ఇక్కడ డ్రాగ్ చేయండి",
      "documents.click_browse": "లేదా బ్రౌజ్ చేయడానికి క్లిక్ చేయండి",
      "documents.category": "పత్రం వర్గం",
      "documents.upload_btn": "పత్రాన్ని ప్రాసెస్ చేయండి",
      "documents.uploaded_records": "అప్‌లోడ్ చేసిన వైద్య రికార్డులు",
      "documents.empty": "ఇంకా పత్రాలు అప్‌లోడ్ కాలేదు.",
      "chat.title": "AI క్లినికల్ అసిస్టెంట్",
      "chat.subtitle": "డివైస్‌పై సురక్షితంగా పనిచేసే AI అసిస్టెంట్",
      "chat.clear": "చాట్ క్లియర్ చేయండి",
      "chat.welcome_msg": "నమస్కారం! నేను మీ గోప్యత-ప్రథమ క్లినికల్ AI అసిస్టెంట్‌ని. మీ ల్యాబ్ ఫలితాలు మరియు మందుల గురించి నన్ను అడగండి.",
      "chat.qp_glucose": "తాజా బ్లడ్ షుగర్",
      "chat.qp_summary": "ల్యాబ్ ఫలితాల సారాంశం",
      "chat.qp_meds": "మందుల షెడ్యూల్",
      "chat.placeholder": "మీ రికార్డుల గురించి ప్రశ్న అడగండి...",
      "chat.send": "పంపండి",
      "audit.title": "HL7 FHIR ఆడిట్ లాగ్స్",
      "audit.subtitle": "HIPAA & ABDM వర్తింపు లాగ్",
      "audit.empty": "ఇంకా ఆడిట్ లాగ్‌లు లేవు.",
      "emergency.title": "ఆఫ్‌లైన్ ఎమర్జెన్సీ పాస్",
      "emergency.subtitle": "ఇంటర్నెట్ లేకుండా అత్యవసర సహాయం",
      "emergency.scan_title": "అత్యవసర సమాచారం కోసం స్కాన్ చేయండి",
      "emergency.scan_subtitle": "కార్డును చదవడానికి ఫోన్ కెమెరాతో స్కాన్ చేయండి",
      "emergency.print_card": "కార్డును ప్రింట్ చేయండి",
      "emergency.test_offline": "ఆఫ్‌లైన్ వీక్షణను పరీక్షించండి",
      "emergency.triage_included": "చేర్చబడిన వివరాలు",
      "emergency.triage_blood": "రక్త సమూహం & ABO అనుకూలత",
      "emergency.triage_allergies": "తీవ్రమైన అలెర్జీ హెచ్చరికలు",
      "emergency.triage_conditions": "దీర్ఘకాలిక సమస్యలు & మందులు",
      "emergency.triage_call": "1-టచ్ సంరక్షకుల కాల్ బ్రిడ్జ్",
      "emergency.triage_crypto": "AES ఎన్‌క్రిప్షన్ రక్షణ",
      "modal.add_member_title": "కుటుంబ సభ్యుడి వాల్ట్‌ను చేర్చండి",
      "modal.edit_profile_title": "ప్రొఫైల్ & ఎమర్జెన్సీ పరిచయాలను సవరించండి",
      "modal.edit_profile_subtitle": "ముఖ్యమైన వైద్య వివరాలు మరియు కనీసం 2 పరిచయాలను నమోదు చేయండి",
      "modal.cancel": "రద్దు చేయండి",
      "modal.save_profile": "ప్రొఫైల్ భద్రపరచండి",
      "modal.create_vault": "వాల్ట్ సృష్టించండి",
      "offline.title": "ఆఫ్‌లైన్ మెడికల్ కార్డ్",
      "offline.subtitle": "డివైస్‌లో సురక్షితంగా భద్రపరచబడింది",
      "offline.emergency_badge": "ఎమర్జెన్సీ",
      "offline.patient_name": "రోగి పేరు",
      "offline.blood_group": "రక్త సమూహం",
      "offline.allergies": "తీవ్రమైన అలెర్జీలు",
      "offline.conditions": "దీర్ఘకాలిక సమస్యలు",
      "offline.medications": "ప్రస్తుత మందులు",
      "offline.caregiver_contacts": "సంరక్షకుల ఎమర్జెన్సీ పరిచయాలు",
      "offline.emergency_card_link": "ఎమర్జెన్సీ కార్డ్ లింక్",
      "contact.primary": "ప్రాథమిక పరిచయం",
      "contact.secondary": "ద్వితీయ పరిచయం",
      "contact.alternative": "ప్రత్యామ్నాయ పరిచయం",
      "contact.call": "కాల్ చేయండి",
      "contact.caregiver": "సంరక్షకుడు",
      "rel.self": "స్వయంగా",
      "rel.father": "తండ్రి",
      "rel.mother": "తల్లి",
      "rel.spouse": "జీవిత భాగస్వామి",
      "rel.child": "పిల్లలు",
      "rel.parent": "తల్లిదండ్రులు",
      "rel.sibling": "తోబుట్టువు",
      "rel.friend": "స్నేహితుడు",
      "rel.other": "ఇతర",
      "status.active": "యాక్టివ్",
      "status.disabled": "డిసేబుల్"
    },
    mr: {
      "app.name": "आधार हेल्थ ब्रिज",
      "app.tagline": "सार्वत्रिक डिजिटल आरोग्य व्हॉल्ट आणि AI क्लिनिकल सहाय्यक",
      "nav.online": "ऑनलाइन",
      "nav.offline": "ऑफलाइन मोड",
      "nav.install": "अॅप स्थापित करा",
      "nav.overview": "आढावा आणि महत्त्वाची लक्षणे",
      "nav.biomarkers": "लॅब बायोमार्कर्स",
      "nav.documents": "वैद्यकीय कागदपत्रे",
      "nav.chat": "स्थानिक RAG AI",
      "nav.audit": "ऑडिट ट्रेल",
      "nav.emergency": "आपत्कालीन QR",
      "nav.logout": "लॉग-आउट",
      "auth.title": "डिजिटल व्हॉल्टमध्ये प्रवेश करा",
      "auth.subtitle": "OAuth 2.0 / Argon2id सुरक्षित क्रेडेन्शियल्ससह प्रमाणीकृत करा.",
      "auth.username": "वापरकर्तानाव किंवा आभा आयडी",
      "auth.password": "मास्टर व्हॉल्ट पासवर्ड",
      "auth.signin": "व्हॉल्टमध्ये साइन इन करा",
      "auth.signup": "नवीन खाते तयार करा",
      "auth.init_vault": "नवीन रुग्ण व्हॉल्ट सुरू करा",
      "auth.quick_demo": "जलद डेमो",
      "vault.active_vault": "सक्रिय व्हॉल्ट",
      "vault.add_member_btn": "+ सदस्य जोडा",
      "vault.export_fhir": "FHIR R4 बंडल निर्यात करा",
      "vault.full_name": "पूर्ण नाव",
      "vault.relation": "नाते",
      "vault.blood_group": "रक्तगट",
      "overview.title": "रुग्ण क्लिनिकल प्रोफाइल",
      "overview.subtitle": "HL7 FHIR R4 अनुरूप वैयक्तिक आरोग्य नोंद",
      "overview.edit_profile": "प्रोफाइल आणि संपर्क संपादित करा",
      "overview.emergency_pass": "आपत्कालीन पास",
      "overview.abo_verified": "ABO/Rh सत्यापित",
      "overview.primary_emergency": "प्राथमिक आपत्कालीन संपर्क",
      "overview.call_primary": "प्राथमिकला कॉल करा",
      "overview.emergency_readiness": "आपत्कालीन सज्जता",
      "overview.scans_allowed": "पॅरामेडिक QR स्कॅन अनुमती आहे",
      "overview.caregiver_contacts_title": "आपत्कालीन काळजीवाहक संपर्क (बचावासाठी किमान २)",
      "overview.manage_contacts": "संपर्क व्यवस्थापित करा",
      "overview.allergies": "गंभीर ॲलर्जी",
      "overview.conditions": "तीव्र आजार",
      "overview.medications": "सक्रिय औषधे",
      "overview.none_reported": "काहीही नोंदवले नाही",
      "overview.emergency_contact": "आपत्कालीन संपर्क",
      "overview.no_phone": "फोन नंबर नाही",
      "overview.no_contacts_warning": "कोणताही काळजीवाहक संपर्क नोंदवला नाही",
      "overview.no_contacts_desc": "किमान २ आपत्कालीन संपर्क जोडा जेणेकरून प्रथम प्रतिसादकर्ते आपल्या कुटुंबाशी संपर्क साधू शकतील.",
      "overview.add_contacts_btn": "२ आपत्कालीन संपर्क जोडा",
      "biomarkers.title": "काढलेले क्लिनिकल बायोमार्कर्स",
      "biomarkers.subtitle": "PDF अहवालांमधून काढलेले HL7 FHIR निरीक्षण रेकॉर्ड",
      "biomarkers.search_placeholder": "🔍 बायोमार्कर्स शोधा (उदा. ग्लुकोज)...",
      "biomarkers.empty": "अद्याप कोणतेही आरोग्य मेट्रिक्स काढले नाहीत. लॅब रिपोर्ट PDF अपलोड करा.",
      "documents.title": "वैद्यकीय कागदपत्रे अंतर्ग्रहण",
      "documents.subtitle": "सुरक्षित स्थानिक PDF विश्लेषण आणि वेक्टर अनुक्रमणिका",
      "documents.drag_drop": "वैद्यकीय अहवाल PDF येथे ड्रॅग आणि ड्रॉप करा",
      "documents.click_browse": "किंवा ब्राउझ करण्यासाठी क्लिक करा",
      "documents.category": "कागदपत्र श्रेणी",
      "documents.upload_btn": "कागदपत्र प्रक्रिया आणि अनुक्रमित करा",
      "documents.uploaded_records": "अपलोड केलेले वैद्यकीय रेकॉर्ड",
      "documents.empty": "अद्याप कोणतीही कागदपत्रे अपलोड केलेली नाहीत.",
      "chat.title": "गोपनीयता-प्रथम AI क्लिनिकल सहाय्यक",
      "chat.subtitle": "डिव्हाइसवर स्थानिक पातळीवर चालणारा AI सहाय्यक",
      "chat.clear": "चॅट साफ करा",
      "chat.welcome_msg": "नमस्कार! मी तुमचा AI क्लिनिकल सहाय्यक आहे. तुमच्या अहवालांबद्दल आणि औषधांबद्दल मला विचारा.",
      "chat.qp_glucose": "नवीनतम रक्त शर्करा",
      "chat.qp_summary": "लॅब निकालांचा सारांश",
      "chat.qp_meds": "औषध वेळापत्रक",
      "chat.placeholder": "तुमच्या रेकॉर्डबद्दल प्रश्न विचारा...",
      "chat.send": "पाठवा",
      "audit.title": "HL7 FHIR ऑडिट ट्रेल",
      "audit.subtitle": "HIPAA आणि ABDM अनुपालन पडताळणी लॉग",
      "audit.empty": "अद्याप कोणतेही ऑडिट लॉग नोंदवले नाहीत.",
      "emergency.title": "ऑफलाइन पॅरामेडिक आपत्कालीन पास",
      "emergency.subtitle": "इंटरनेटशिवाय प्रथम प्रतिसादकर्त्यांसाठी ग्लास-ब्रेकर प्रवेश",
      "emergency.scan_title": "आपत्कालीन वैद्यकीय माहितीसाठी स्कॅन करा",
      "emergency.scan_subtitle": "ट्रायज कार्ड वाचण्यासाठी फोन कॅमेऱ्याने स्कॅन करा",
      "emergency.print_card": "कार्ड प्रिंट करा",
      "emergency.test_offline": "ऑफलाइन दृश्य चाचणी करा",
      "emergency.triage_included": "समाविष्ट ट्रायज माहिती",
      "emergency.triage_blood": "रक्तगट आणि ABO सुसंगतता",
      "emergency.triage_allergies": "गंभीर ॲलर्जी आणि इशारे",
      "emergency.triage_conditions": "तीव्र आजार आणि औषधे",
      "emergency.triage_call": "१-टच आपत्कालीन काळजीवाहक कॉल ब्रिज",
      "emergency.triage_crypto": "AES एन्क्रिप्शन संरक्षण",
      "modal.add_member_title": "कुटुंब सदस्य व्हॉल्ट जोडा",
      "modal.edit_profile_title": "प्रोफाइल आणि आपत्कालीन संपर्क संपादित करा",
      "modal.edit_profile_subtitle": "महत्त्वाची वैद्यकीय माहिती आणि किमान २ काळजीवाहक संपर्क प्रविष्ट करा",
      "modal.cancel": "रद्द करा",
      "modal.save_profile": "प्रोफाइल जतन करा",
      "modal.create_vault": "व्हॉल्ट तयार करा",
      "offline.title": "ऑफलाइन वैद्यकीय कार्ड",
      "offline.subtitle": "स्थानिक डिव्हाइसवर सुरक्षितपणे साठवले आहे",
      "offline.emergency_badge": "आपत्कालीन",
      "offline.patient_name": "रुग्णाचे नाव",
      "offline.blood_group": "रक्तगट",
      "offline.allergies": "गंभीर ॲलर्जी",
      "offline.conditions": "तीव्र आजार",
      "offline.medications": "सक्रिय औषधे",
      "offline.caregiver_contacts": "काळजीवाहक आपत्कालीन संपर्क",
      "offline.emergency_card_link": "आपत्कालीन कार्ड लिंक",
      "contact.primary": "प्राथमिक संपर्क",
      "contact.secondary": "द्वितीयक संपर्क",
      "contact.alternative": "पर्यायी संपर्क",
      "contact.call": "कॉल करा",
      "contact.caregiver": "काळजीवाहक",
      "rel.self": "स्वतः",
      "rel.father": "वडील",
      "rel.mother": "आई",
      "rel.spouse": "जोडीदार",
      "rel.child": "मूल",
      "rel.parent": "पालक",
      "rel.sibling": "भावंड",
      "rel.friend": "मित्र",
      "rel.other": "इतर",
      "status.active": "सक्रिय",
      "status.disabled": "अक्षम"
    }
  };

  function t(key, params = {}) {
    const currentDict = DICTIONARIES[currentLang] || DICTIONARIES['en'];
    let text = currentDict[key] || DICTIONARIES['en'][key] || key;

    if (params && typeof params === 'object') {
      Object.keys(params).forEach((paramKey) => {
        text = text.replace(new RegExp(`{${paramKey}}`, 'g'), params[paramKey]);
      });
    }

    return text;
  }

  function translateRelation(rel) {
    if (!rel) return t('rel.self');
    const lower = String(rel).toLowerCase().trim();
    if (lower.includes('father') || lower.includes('पिता') || lower.includes('বাবা') || lower.includes('தந்தை') || lower.includes('తండ్రి') || lower.includes('वडील')) return t('rel.father');
    if (lower.includes('mother') || lower.includes('माता') || lower.includes('মা') || lower.includes('தாய்') || lower.includes('తల్లి') || lower.includes('आई')) return t('rel.mother');
    if (lower.includes('spouse') || lower.includes('husband') || lower.includes('wife') || lower.includes('जीवनसाथी') || lower.includes('স্বামী') || lower.includes('துணைவர்') || lower.includes('భాగస్వామి') || lower.includes('जोडीदार')) return t('rel.spouse');
    if (lower.includes('child') || lower.includes('son') || lower.includes('daughter') || lower.includes('बच्चा') || lower.includes('সন্তান') || lower.includes('குழந்தை') || lower.includes('పిల్లలు') || lower.includes('मूल')) return t('rel.child');
    if (lower.includes('parent') || lower.includes('अभिभावक') || lower.includes('পিতা-মাতা') || lower.includes('பெற்றோர்') || lower.includes('తల్లిదండ్రులు') || lower.includes('पालक')) return t('rel.parent');
    if (lower.includes('sibling') || lower.includes('brother') || lower.includes('sister') || lower.includes('भाई') || lower.includes('बहन') || lower.includes('ভাই') || lower.includes('বোন') || lower.includes('உடன்பிறப்பு') || lower.includes('తోబుట్టువు') || lower.includes('भावंड')) return t('rel.sibling');
    if (lower.includes('friend') || lower.includes('मित्र') || lower.includes('दोस्त') || lower.includes('বন্ধু') || lower.includes('நண்பர்') || lower.includes('స్నేహితుడు')) return t('rel.friend');
    if (lower.includes('self') || lower.includes('स्वयं') || lower.includes('নিজে') || lower.includes('சுய') || lower.includes('స్వయంగా') || lower.includes('स्वतः')) return t('rel.self');
    if (lower.includes('primary') || lower.includes('प्राथमिक') || lower.includes('প্রাথমিক') || lower.includes('முதன்மை') || lower.includes('ప్రాథమిక')) return t('contact.primary');
    if (lower.includes('secondary') || lower.includes('द्वितीयक') || lower.includes('দ্বিতীয়') || lower.includes('இரண்டாம்') || lower.includes('ద్వితీయ')) return t('contact.secondary');
    if (lower.includes('alternative') || lower.includes('doctor') || lower.includes('वैकल्पिक') || lower.includes('বিকল্প') || lower.includes('மாற்று') || lower.includes('ప్రత్యామ్నాయ') || lower.includes('पर्यायी')) return t('contact.alternative');
    return rel;
  }

  function updateButtonPills(activeLang) {
    document.querySelectorAll('.ahb-lang-btn').forEach((btn) => {
      const isSelected = btn.dataset.lang === activeLang;
      btn.classList.toggle('active-lang', isSelected);
      if (isSelected) {
        btn.style.setProperty('background', '#0d9488', 'important');
        btn.style.setProperty('color', '#ffffff', 'important');
        btn.style.setProperty('font-weight', '800', 'important');
        btn.style.setProperty('box-shadow', '0 2px 10px rgba(13, 148, 136, 0.6)', 'important');
      } else {
        btn.style.setProperty('background', 'transparent', 'important');
        btn.style.setProperty('color', '#94a3b8', 'important');
        btn.style.setProperty('font-weight', '700', 'important');
        btn.style.setProperty('box-shadow', 'none', 'important');
      }
    });
  }

  function setLanguage(lang) {
    if (!DICTIONARIES[lang]) lang = 'en';
    currentLang = lang;
    localStorage.setItem('hb_lang', lang);
    document.documentElement.lang = lang;

    // 1. Instantly update button highlight
    updateButtonPills(lang);

    // 2. Instantly translate entire DOM
    applyTranslations();

    // 3. Dispatch language changed event
    document.dispatchEvent(new CustomEvent('ahb:language-changed', { detail: { lang } }));
  }

  function applyTranslations() {
    const currentDict = DICTIONARIES[currentLang] || DICTIONARIES['en'];
    const fallbackDict = DICTIONARIES['en'];

    // Update all elements with data-i18n
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      const text = currentDict[key] || fallbackDict[key];
      if (text) {
        if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
          el.setAttribute('placeholder', text);
        } else {
          el.textContent = text;
        }
      }
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      const text = currentDict[key] || fallbackDict[key];
      if (text) {
        el.setAttribute('placeholder', text);
      }
    });

    // Update title attributes
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const key = el.getAttribute('data-i18n-title');
      const text = currentDict[key] || fallbackDict[key];
      if (text) {
        el.setAttribute('title', text);
      }
    });

    // Sync button highlight
    updateButtonPills(currentLang);
  }

  function injectLanguageSelector() {
    if (document.getElementById('ahb-lang-wrapper')) {
      updateButtonPills(currentLang);
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.id = 'ahb-lang-wrapper';
    wrapper.style.cssText = 'display:inline-flex;align-items:center;gap:4px;background:rgba(15,23,42,0.85);border:1px solid rgba(255,255,255,0.15);border-radius:10px;padding:3px 5px;margin-right:8px;backdrop-filter:blur(10px);box-shadow:0 4px 12px rgba(0,0,0,0.3);';

    SUPPORTED_LANGUAGES.forEach((lang) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ahb-lang-btn';
      btn.dataset.lang = lang.code;
      btn.title = `${lang.full} (${lang.native})`;
      btn.style.cssText = 'padding:4px 8px;border-radius:6px;border:none;font-size:11px;font-weight:800;cursor:pointer;background:transparent;color:#94a3b8;font-family:inherit;transition:all 0.15s ease;';
      btn.textContent = lang.label;

      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setLanguage(lang.code);
      });

      wrapper.appendChild(btn);
    });

    const navActions = document.querySelector('.nav-actions');
    if (navActions) {
      navActions.insertBefore(wrapper, navActions.firstChild);
    }

    updateButtonPills(currentLang);
    applyTranslations();
  }

  const i18nInstance = {
    t,
    translateRelation,
    setLanguage,
    applyTranslations,
    getSupportedLanguages: () => SUPPORTED_LANGUAGES,
    getCurrentLanguage: () => currentLang
  };

  window.AHB_I18N = i18nInstance;
  window.HealthBridgeI18n = i18nInstance;

  document.addEventListener('DOMContentLoaded', () => {
    injectLanguageSelector();
    applyTranslations();
  });

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    injectLanguageSelector();
    applyTranslations();
  }

  return i18nInstance;
})();
