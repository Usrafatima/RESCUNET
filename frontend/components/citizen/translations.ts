// ─── RescuNet Citizen Dashboard Translations (English & Roman Urdu) ───

export type Language = "en" | "ur";

export interface Translations {
  // Header & Hotlines
  hotlineBar: string;
  hotlineAmbulance: string;
  hotlinePolice: string;
  hotlineFire: string;
  portalTitle: string;
  portalBadge: string;
  portalSubtitle: string;
  secureIntake: string;
  languageSelect: string;

  // Tabs
  tabReport: string;
  tabTrack: string;
  tabGuide: string;

  // Network Status
  netOnline: string;
  netEdge: string;
  netOffline: string;
  netChecking: string;
  netRefresh: string;

  // Form Section Headers
  reportTitle: string;
  reportSubtitle: string;
  stepType: string;
  stepLocation: string;
  stepPeople: string;
  stepDesc: string;
  required: string;

  // Voice Reporting
  voiceButton: string;
  voiceListening: string;
  voiceStop: string;
  voiceSupportedNotice: string;
  voiceUnsupportedNotice: string;
  voicePermissionDenied: string;
  voiceNoSpeech: string;
  voiceTranscriptLabel: string;
  voiceTranscriptHint: string;
  voiceSuggestedCategory: string;
  voiceApplyToForm: string;
  voiceClear: string;
  voiceReadAloud: string;
  voiceStopReadAloud: string;
  voiceReviewTitle: string;
  voiceReviewSubtitle: string;
  voiceConfirmSend: string;
  voiceEditAgain: string;
  voiceLocationConfirmPrompt: string;
  voicePeopleConfirmPrompt: string;

  // Emergency Categories
  catMedical: string;
  catMedicalDesc: string;
  catFire: string;
  catFireDesc: string;
  catFlood: string;
  catFloodDesc: string;
  catAccident: string;
  catAccidentDesc: string;
  catOther: string;
  catOtherDesc: string;

  // Location
  shareGps: string;
  detectingGps: string;
  gpsAcquired: string;
  gpsDenied: string;
  latitudeLabel: string;
  longitudeLabel: string;
  landmarkLabel: string;
  landmarkPlaceholder: string;
  demoAreasLabel: string;

  // People Affected
  peoplePerson: string;
  peoplePlural: string;

  // Description & Urgency
  descPlaceholderMedical: string;
  descPlaceholderFire: string;
  descPlaceholderFlood: string;
  descPlaceholderAccident: string;
  descPlaceholderOther: string;
  lifeThreatLabel: string;
  lifeThreatDesc: string;

  // Form Actions & Validation
  submitButton: string;
  submittingButton: string;
  validationDescRequired: string;
  validationLatRange: string;
  validationLngRange: string;
  disclaimerIntake: string;

  // Confirmation Screen
  confirmTitle: string;
  confirmSubtitle: string;
  confirmRefLabel: string;
  confirmViaCentral: string;
  confirmViaEdge: string;
  confirmSummaryTitle: string;
  confirmSummaryCategory: string;
  confirmSummaryAffected: string;
  confirmSummaryCoords: string;
  confirmSummaryPriority: string;
  confirmLifeThreat: string;
  confirmStandard: string;
  confirmTrackBtn: string;
  confirmSubmitAnother: string;
  confirmSafetyReminder: string;

  // Status Tracker
  trackTitle: string;
  trackSubtitle: string;
  trackPlaceholder: string;
  trackButton: string;
  trackSearching: string;
  trackNotFound: string;
  trackEdgeBufferedTitle: string;
  trackEdgeBufferedDesc: string;
  trackEdgeNextStep: string;
  trackRefLabel: string;
  trackReportedAt: string;
  trackAffectedLabel: string;
  trackUpdatedNow: string;
  trackProgressTitle: string;
  trackStepQueued: string;
  trackStepQueuedDesc: string;
  trackStepTriage: string;
  trackStepTriageDesc: string;
  trackStepPlan: string;
  trackStepPlanDesc: string;
  trackStepDispatched: string;
  trackStepDispatchedDesc: string;
  trackStepResolved: string;
  trackStepResolvedDesc: string;
  statusBadgeQueued: string;
  statusBadgeTriage: string;
  statusBadgeApproval: string;
  statusBadgeDispatched: string;
  statusBadgeResolved: string;
  statusBadgeCancelled: string;
  statusMsgQueued: string;
  statusMsgProcessing: string;
  statusMsgApproval: string;
  statusMsgDispatched: string;
  statusMsgResolved: string;
  statusMsgCancelled: string;
  trackPrivacyNotice: string;
  trackBackToReport: string;

  // Survival Guide
  guideTitle: string;
  guideSubtitle: string;
  guideCallHotline: string;
  guideDoTitle: string;
  guideDontTitle: string;
  guideNotice: string;

  // Info Cards
  cardTriageTitle: string;
  cardTriageDesc: string;
  cardEdgeTitle: string;
  cardEdgeDesc: string;
  cardApprovalTitle: string;
  cardApprovalDesc: string;

  // Footer
  footerDisclaimer: string;
  footerRights: string;
}

export const TRANSLATIONS: Record<Language, Translations> = {
  en: {
    // Header & Hotlines
    hotlineBar: "Life-Threatening Emergency? Call National Emergency Services Immediately",
    hotlineAmbulance: "AMBULANCE: 1122 / 112",
    hotlinePolice: "POLICE: 15 / 911",
    hotlineFire: "FIRE: 16",
    portalTitle: "RESCUNET",
    portalBadge: "Public Portal",
    portalSubtitle: "Citizen Emergency Reporting & Coordination",
    secureIntake: "Secure Citizen Intake",
    languageSelect: "Language",

    // Tabs
    tabReport: "Report Emergency (SOS)",
    tabTrack: "Track Incident Status",
    tabGuide: "Survival Guidance",

    // Network Status
    netOnline: "Central Dispatch Online",
    netEdge: "Edge Gateway Active (Buffer Mode)",
    netOffline: "Network Offline",
    netChecking: "Checking Network...",
    netRefresh: "Re-check network connectivity",

    // Form Section Headers
    reportTitle: "Report an Emergency (SOS)",
    reportSubtitle: "Provide details below to submit a priority rescue report to RescuNet.",
    stepType: "1. Select Emergency Type",
    stepLocation: "2. Emergency Location",
    stepPeople: "3. Number of People Affected",
    stepDesc: "4. Emergency Description",
    required: "*",

    // Voice Reporting
    voiceButton: "Speak Your Emergency",
    voiceListening: "Listening... Describe your emergency clearly",
    voiceStop: "Stop Recording",
    voiceSupportedNotice: "Voice speech recognition active. Speak clearly into your device microphone.",
    voiceUnsupportedNotice: "Voice recognition is not supported by this browser. Please type your description manually.",
    voicePermissionDenied: "Microphone permission was denied. Please allow microphone access or use the manual text form.",
    voiceNoSpeech: "No speech was detected. Please click the button and speak again.",
    voiceTranscriptLabel: "Recognized Voice Transcript (Editable)",
    voiceTranscriptHint: "You can edit, fix names, or add details to the transcript above before proceeding.",
    voiceSuggestedCategory: "Suggested Emergency Category:",
    voiceApplyToForm: "Apply Voice Report to Form",
    voiceClear: "Clear Voice Transcript",
    voiceReadAloud: "Read Aloud",
    voiceStopReadAloud: "Stop Read Aloud",
    voiceReviewTitle: "Review Emergency Report Before Submission",
    voiceReviewSubtitle: "Please verify all details carefully. An explicit confirmation is required before dispatch intake.",
    voiceConfirmSend: "Confirm & Transmit SOS Report",
    voiceEditAgain: "Back to Editing",
    voiceLocationConfirmPrompt: "Please confirm your location coordinates and nearby landmark:",
    voicePeopleConfirmPrompt: "Please confirm number of people affected:",

    // Emergency Categories
    catMedical: "Medical",
    catMedicalDesc: "Severe injury, heart attack, unconsciousness, heavy bleeding",
    catFire: "Fire",
    catFireDesc: "Active flames, dense smoke, explosion, trapped by fire",
    catFlood: "Flood",
    catFloodDesc: "Rising floodwaters, submerged roads, trapped in vehicle or home",
    catAccident: "Accident",
    catAccidentDesc: "Major road collision, structural collapse, industrial mishap",
    catOther: "Other",
    catOtherDesc: "Hazmat leak, building instability, missing persons, weather hazard",

    // Location
    shareGps: "Share My Current GPS Location",
    detectingGps: "Detecting GPS...",
    gpsAcquired: "GPS location acquired",
    gpsDenied: "Location permission denied. Please enter coordinates manually.",
    latitudeLabel: "Latitude Coordinate",
    longitudeLabel: "Longitude Coordinate",
    landmarkLabel: "Street, Building, or Recognizable Landmark (Optional)",
    landmarkPlaceholder: "e.g. Near City General Hospital, Block 4 or Main Highway Mile 12",
    demoAreasLabel: "Quick Demo Areas:",

    // People Affected
    peoplePerson: "person",
    peoplePlural: "people",

    // Description & Urgency
    descPlaceholderMedical: "e.g. 52-year-old male experiencing acute chest pain and shortness of breath. Conscious but unable to stand.",
    descPlaceholderFire: "e.g. Electrical fire spreading on the 2nd floor of a residential building. Thick black smoke, 3 people trapped on balcony.",
    descPlaceholderFlood: "e.g. Flash flood rapidly rising. Water level is chest-deep on ground floor. Family stranded on rooftop.",
    descPlaceholderAccident: "e.g. Two-vehicle collision at intersection. One car overturned. Passenger pinned inside driver seat.",
    descPlaceholderOther: "e.g. Strong chemical smell in neighborhood causing nausea and dizziness. Power lines down across road.",
    lifeThreatLabel: "Immediate Life-Threatening Danger or Entrapment",
    lifeThreatDesc: "Check this if anyone is unconscious, not breathing, pinned under debris, or surrounded by active fire/water.",

    // Form Actions & Validation
    submitButton: "SUBMIT EMERGENCY REPORT (SOS)",
    submittingButton: "Transmitting SOS Report...",
    validationDescRequired: "Please provide a brief description of the emergency.",
    validationLatRange: "Please provide a valid latitude between -90 and 90.",
    validationLngRange: "Please provide a valid longitude between -180 and 180.",
    disclaimerIntake: "By submitting, this incident enters RescuNet’s priority triage queue. No guaranteed municipal 911 dispatch is made unless confirmed by local authorities.",

    // Confirmation Screen
    confirmTitle: "Emergency Report Received",
    confirmSubtitle: "Your emergency report has been logged into the RescuNet coordination queue. Response teams prioritize incoming incidents by urgency and resource proximity.",
    confirmRefLabel: "Your Incident Reference Number",
    confirmViaCentral: "Logged directly into Central Emergency Dispatch.",
    confirmViaEdge: "Queued via Local Edge Gateway — will sync automatically to dispatch.",
    confirmSummaryTitle: "Submitted Details Summary",
    confirmSummaryCategory: "Category:",
    confirmSummaryAffected: "Affected:",
    confirmSummaryCoords: "Coordinates:",
    confirmSummaryPriority: "Priority Flag:",
    confirmLifeThreat: "Life-Threatening",
    confirmStandard: "Standard Urgent",
    confirmTrackBtn: "Track Incident Status Now",
    confirmSubmitAnother: "Submit Another Report",
    confirmSafetyReminder: "Critical Life Safety Reminder: RescuNet coordinates community and simulation emergency resources. If you or someone with you is in immediate life danger, always dial your official national emergency number (112 / 911 / 15) directly.",

    // Status Tracker
    trackTitle: "Emergency Status Tracking",
    trackSubtitle: "Check the real-time coordination status of your submitted emergency report.",
    trackPlaceholder: "Enter Incident Reference (e.g. RSN-000001 or EDGE-000001)",
    trackButton: "Track",
    trackSearching: "Looking up incident records...",
    trackNotFound: "No incident report found with reference",
    trackEdgeBufferedTitle: "Buffered in Local Edge Gateway",
    trackEdgeBufferedDesc: "Your report was recorded by a local edge gateway station. It is queued locally in offline storage and will sync automatically to Central Dispatch as soon as network connectivity is active.",
    trackEdgeNextStep: "When edge connectivity toggles ONLINE or synchronization runs, this packet will receive a permanent central incident ID (RSN-XXXXXX). You can check back with this reference anytime.",
    trackRefLabel: "Incident Reference",
    trackReportedAt: "Reported:",
    trackAffectedLabel: "Affected:",
    trackUpdatedNow: "Updated",
    trackProgressTitle: "Coordination Progress",
    trackStepQueued: "Report Received",
    trackStepQueuedDesc: "Logged in emergency coordination queue",
    trackStepTriage: "Triage Analysis",
    trackStepTriageDesc: "Urgency evaluation and resource capability matching",
    trackStepPlan: "Response Planned",
    trackStepPlanDesc: "Action plan prepared for human coordinator authorization",
    trackStepDispatched: "Response Mobilized",
    trackStepDispatchedDesc: "Assigned response units mobilized towards incident location",
    trackStepResolved: "Incident Resolved",
    trackStepResolvedDesc: "Assistance delivered and scene safety verified",
    statusBadgeQueued: "Queued for Triage",
    statusBadgeTriage: "Under Active Triage",
    statusBadgeApproval: "Coordination Pending",
    statusBadgeDispatched: "Response Dispatched",
    statusBadgeResolved: "Resolved",
    statusBadgeCancelled: "Cancelled",
    statusMsgQueued: "Your emergency report is safely recorded in the queue. RescuNet’s triage engine is prioritizing it based on severity.",
    statusMsgProcessing: "AI triage is analyzing the hazard level, required rescue capabilities, and nearby team availability.",
    statusMsgApproval: "A rescue proposal has been assembled. A human coordinator is currently reviewing and verifying the deployment plan.",
    statusMsgDispatched: "Response coordinator has authorized the assistance plan. Teams and resources are being directed to coordinates.",
    statusMsgResolved: "Response coordinators have logged this incident as resolved. If you require further assistance, please submit a new report.",
    statusMsgCancelled: "This report has been flagged as cancelled or superseded by a duplicate report.",
    trackPrivacyNotice: "Privacy & Safety Protection: For the safety of emergency responders and affected individuals, detailed resource identities, route paths, and third-party reports are kept private within the administrative command console.",
    trackBackToReport: "Submit New Report",

    // Survival Guide
    guideTitle: "Immediate Emergency Guidance",
    guideSubtitle: "Critical life-safety steps to follow while awaiting coordination",
    guideCallHotline: "National Emergency: 112 / 911",
    guideDoTitle: "What to Do Immediately",
    guideDontTitle: "Critical Hazards to Avoid",
    guideNotice: "RescuNet Safety Notice: This guidance is provided for informational survival aid. RescuNet coordinates volunteer & simulation response assets; always follow instructions from local emergency personnel on the ground.",

    // Info Cards
    cardTriageTitle: "Deterministic AI Triage",
    cardTriageDesc: "Every citizen report is analyzed for urgency, hazard types, and affected counts. The system ranks emergencies objectively so critical cases receive priority.",
    cardEdgeTitle: "Offline Edge Gateway",
    cardEdgeDesc: "If cellular networks are disrupted, reports buffer safely in local edge gateways and synchronize automatically when connectivity returns.",
    cardApprovalTitle: "Human Approval Required",
    cardApprovalDesc: "AI proposes responder matches, but human operators in the administrative command dashboard review and verify every response before dispatch.",

    // Footer
    footerDisclaimer: "RescuNet is an independent, AI-assisted emergency coordination project. For immediate life-threatening emergencies, always dial your official national emergency services (112 / 911 / 15 / 1122). Ordinary citizens cannot view other people’s incident details or access administrative dispatch controls.",
    footerRights: "RescuNet Emergency Coordination System • All Citizen Reports Logged Securely",
  },

  ur: {
    // Header & Hotlines
    hotlineBar: "Zindagi ko khatra hai? Fauran Qaumi Emergency Services ko call karain",
    hotlineAmbulance: "AMBULANCE: 1122 / 112",
    hotlinePolice: "POLICE: 15 / 911",
    hotlineFire: "FIRE BRIGADE: 16",
    portalTitle: "RESCUNET",
    portalBadge: "Awami Portal",
    portalSubtitle: "Shehri Emergency Reporting aur Coordination",
    secureIntake: "Mehfooz Shehri Intake",
    languageSelect: "Zaban (Language)",

    // Tabs
    tabReport: "Emergency Report Karain (SOS)",
    tabTrack: "Report Ka Status Maloom Karain",
    tabGuide: "Hifazati Hidayat (Survival Guide)",

    // Network Status
    netOnline: "Central Dispatch Online Hai",
    netEdge: "Edge Gateway Active (Local Buffer)",
    netOffline: "Network Offline Hai",
    netChecking: "Network Check Ho Raha Hai...",
    netRefresh: "Network dobara check karain",

    // Form Section Headers
    reportTitle: "Emergency Ki Report Bhejein (SOS)",
    reportSubtitle: "RescuNet ko fauri madad ke liye darj zail tafseelat faraham karain.",
    stepType: "1. Emergency Ki Qisam Chuniye",
    stepLocation: "2. Emergency Ki Jagah (Location)",
    stepPeople: "3. Mutasira Afraad Ki Tadaad",
    stepDesc: "4. Emergency Ki Wazahat (Description)",
    required: "*",

    // Voice Reporting
    voiceButton: "Awaz Se Report Karain (Speak Your Emergency)",
    voiceListening: "Sun rahay hain... Apni emergency wazeh alfaaz mein bayan karain",
    voiceStop: "Recording Rokhein",
    voiceSupportedNotice: "Voice recognition active hai. Apne mic mein wazeh awaz mein bolein.",
    voiceUnsupportedNotice: "Aap ka browser voice recognition support nahi karta. Barah-e-karam neechay text form mein likh kar bayan karain.",
    voicePermissionDenied: "Microphone ki ijazat nahi mili. Barah-e-karam browser mein mic ki permission allow karain ya text form istemal karain.",
    voiceNoSpeech: "Koi awaz mehsoos nahi hui. Dobara mic button daba kar bolein.",
    voiceTranscriptLabel: "Record Shuda Tehreer (Edit Kar Sakte Hain)",
    voiceTranscriptHint: "Aap is tehreer mein koi bhi ghalti durust kar saktay hain ya mazeed tafseel likh saktay hain.",
    voiceSuggestedCategory: "Tajweez Karda Emergency Qisam:",
    voiceApplyToForm: "Yeh Tehreer Form Mein Shamil Karain",
    voiceClear: "Awaz Ka Record Saaf Karain",
    voiceReadAloud: "Awaz Mein Suniye (Read Aloud)",
    voiceStopReadAloud: "Awaz Rokhein",
    voiceReviewTitle: "Bhejne Se Pehle Report Ka Jaiza Aur Tasdeeq",
    voiceReviewSubtitle: "Barah-e-karam tamam tafseelat ka jaiza lein. Bhejne se pehle aap ki wazeh tasdeeq zaroori hai.",
    voiceConfirmSend: "Tasdeeq Karain Aur SOS Bhejein",
    voiceEditAgain: "Wapis Ja Kar Tabdeeli Karain",
    voiceLocationConfirmPrompt: "Barah-e-karam apni location coordinates aur qareebi nishani ki tasdeeq karain:",
    voicePeopleConfirmPrompt: "Barah-e-karam mutasira afraad ki tadaad ki tasdeeq karain:",

    // Emergency Categories
    catMedical: "Medical / Tibbi Imdad",
    catMedicalDesc: "Shadeed chot, dil ka daura, behoshi, khoon behna, saans ki takleef",
    catFire: "Aag / Fire",
    catFireDesc: "Aag ke sholay, dhuwan, dhamaka, imarat mein phansay afraad",
    catFlood: "Sailaab / Flood",
    catFloodDesc: "Charta hua paani, doobi hui sarak, ghar ya gaari mein phansay afraad",
    catAccident: "Haadsa / Accident",
    catAccidentDesc: "Gaariyon ka tasadum, imarat ka girna, karkhanay ka haadsa",
    catOther: "Deegar / Other",
    catOtherDesc: "Chemical leak, gas ki boo, toota hua bijli ka taar, qudrati aafat",

    // Location
    shareGps: "Meri Maujooda GPS Location Share Karain",
    detectingGps: "GPS Location Maloom Ki Ja Rahi Hai...",
    gpsAcquired: "GPS Location Mil Gayi Hai",
    gpsDenied: "Location ki ijazat nahi mili. Barah-e-karam coordinates khud darj karain.",
    latitudeLabel: "Latitude Coordinate",
    longitudeLabel: "Longitude Coordinate",
    landmarkLabel: "Sarak, Imarat, ya Qareebi Mashhoor Jagah (Ikhtiyari)",
    landmarkPlaceholder: "maslan Civil Hospital ke qareeb, Block 4, ya Shahrah-e-Faisal",
    demoAreasLabel: "Qareebi Mashhoor Ilaiqay:",

    // People Affected
    peoplePerson: "fard",
    peoplePlural: "afraad",

    // Description & Urgency
    descPlaceholderMedical: "maslan 52 saala mareez ko dil mein shadeed dard aur saans lene mein dushwari hai. Hosh mein hain magar kharay nahi ho saktay.",
    descPlaceholderFire: "maslan Rehaishi imarat ki doosri manzil par aag lag gayi hai. Kaala dhuwan uth raha hai, 3 afraad balcony par phansay hain.",
    descPlaceholderFlood: "maslan Sailaabi paani taizi se barh raha hai. Ground floor par kamar tak paani hai. Khandan chhat par madad ka muntazir hai.",
    descPlaceholderAccident: "maslan Chowk par do gaariyon ka shadeed tasadum hua hai. Aik gaari ulat gayi hai aur driver andar phansa hua hai.",
    descPlaceholderOther: "maslan Ilaiqay mein chemical ya gas ki shadeed boo phail rahi hai jis se ulti aur chakkar aa rahay hain.",
    lifeThreatLabel: "Zindagi Ko Fauri Khatra ya Malbay Mein Phansay Afraad",
    lifeThreatDesc: "Agar koi behosh hai, saans band hai, malbay talay daba hai ya aag/paani mein ghira hai to isay zaroor tick karain.",

    // Form Actions & Validation
    submitButton: "EMERGENCY REPORT BHEJEIN (SOS)",
    submittingButton: "SOS Report Bheji Ja Rahi Hai...",
    validationDescRequired: "Barah-e-karam emergency ki mukhtasir wazahat zaroor likhein.",
    validationLatRange: "Barah-e-karam durust latitude (-90 se 90 ke darmiyan) darj karain.",
    validationLngRange: "Barah-e-karam durust longitude (-180 se 180 ke darmiyan) darj karain.",
    disclaimerIntake: "Report bhejne par yeh RescuNet ke triage queue mein shamil ho jaye gi. Sarkari 911 dispatch ki zamanat nahi hai jab tak muqami idaray tasdeeq na karain.",

    // Confirmation Screen
    confirmTitle: "Aap Ki Emergency Report Wasool Ho Gayi Hai",
    confirmSubtitle: "Aap ki report RescuNet coordination queue mein darj kar li gayi hai. Rescue teams shiddat aur faaslay ke mutabiq tarjeeh deti hain.",
    confirmRefLabel: "Aap Ka Incident Reference Number",
    confirmViaCentral: "Central Emergency Dispatch mein barah-e-raast darj ho gaya hai.",
    confirmViaEdge: "Local Edge Gateway par mehfooz ho gaya hai — network aatay hi khud-ba-khud sync ho jaye ga.",
    confirmSummaryTitle: "Darj Karda Tafseelat Ka Khulasa",
    confirmSummaryCategory: "Qisam:",
    confirmSummaryAffected: "Mutasira Afraad:",
    confirmSummaryCoords: "Coordinates:",
    confirmSummaryPriority: "Tarjeehi Flag:",
    confirmLifeThreat: "Zindagi Ko Khatra (Life-Threatening)",
    confirmStandard: "Aam Emergency (Standard Urgent)",
    confirmTrackBtn: "Abhi Incident Ka Status Check Karain",
    confirmSubmitAnother: "Aik Aur Report Darj Karain",
    confirmSafetyReminder: "Ahem Hifazati Yad-dehani: RescuNet falahi aur simulation coordination system hai. Agar zindagi ko fauri khatra ho to hamesha qaumi emergency numbers (1122 / 112 / 15) par direct call karain.",

    // Status Tracker
    trackTitle: "Emergency Status Ki Maloomat",
    trackSubtitle: "Apni darj karda report ki live coordination status yahan dekhein.",
    trackPlaceholder: "Incident Reference ID Darj Karain (maslan RSN-000001 ya EDGE-000001)",
    trackButton: "Status Dekhein",
    trackSearching: "Records talash kiye ja rahay hain...",
    trackNotFound: "Is reference number ke sath koi record nahi mila",
    trackEdgeBufferedTitle: "Local Edge Gateway Par Mehfooz Hai",
    trackEdgeBufferedDesc: "Aap ki report muqami edge gateway ne record kar li hai. Yeh offline storage mein mehfooz hai aur network bahaal hotay hi Central Dispatch ko bhej di jaye gi.",
    trackEdgeNextStep: "Jab edge station ONLINE hoga, is report ko permanent central ID (RSN-XXXXXX) mil jaye gi. Aap kisi bhi waqt is reference se status check kar saktay hain.",
    trackRefLabel: "Incident Reference",
    trackReportedAt: "Waqt-e-Report:",
    trackAffectedLabel: "Mutasira Afraad:",
    trackUpdatedNow: "Taza-tareen",
    trackProgressTitle: "Karwai Ki Raftaar (Coordination Progress)",
    trackStepQueued: "Report Wasool Hui",
    trackStepQueuedDesc: "Emergency queue mein darj ho chuki hai",
    trackStepTriage: "Triage Jaiza",
    trackStepTriageDesc: "Shiddat ka tayyun aur zaroori team ki nishandahi",
    trackStepPlan: "Mansooba Tayyar",
    trackStepPlanDesc: "Human coordinator ki tasdeeq ke liye pesh",
    trackStepDispatched: "Team Rawana",
    trackStepDispatchedDesc: "Mutasira jagah ke liye rescue team rawana ho chuki hai",
    trackStepResolved: "Khatma / Hal Shuda",
    trackStepResolvedDesc: "Madad pohancha di gayi aur jagah ko mehfooz qarar diya gaya",
    statusBadgeQueued: "Triage Ki Saf Mein",
    statusBadgeTriage: "Triage Jaari Hai",
    statusBadgeApproval: "Tasdeeq Zer-e-Ghor",
    statusBadgeDispatched: "Team Rawana Hai",
    statusBadgeResolved: "Hal Ho Chuka Hai",
    statusBadgeCancelled: "Mansookh",
    statusMsgQueued: "Aap ki report safely record ho chuki hai. RescuNet ka triage engine isay shiddat ke mutabiq tarjeeh de raha hai.",
    statusMsgProcessing: "AI triage khatray ki shiddat aur qareebi team ki salahiyat ka jaiza le raha hai.",
    statusMsgApproval: "Rescue mansooba tayyar hai. Human coordinator is waqt is ki tasdeeq aur review kar raha hai.",
    statusMsgDispatched: "Response coordinator ne rescue team rawana kar di hai. Teams coordinates ki taraf ja rahi hain.",
    statusMsgResolved: "Emergency coordinators ne is case ko hal shuda mark kar diya hai. Agar mazeed madad darkar ho to nayi report karein.",
    statusMsgCancelled: "Yeh report duplicate honay ki bina par mansookh kar di gayi hai.",
    trackPrivacyNotice: "Hifazat Aur Razdari: Responders aur mutasira afraad ki salamti ke liye team ke azaa ke naam aur rastey administrative control room tak mehdood rakhay jatay hain.",
    trackBackToReport: "Nayi Report Bhejein",

    // Survival Guide
    guideTitle: "Fauri Hifazati Hidayat",
    guideSubtitle: "Rescue team aane tak zindagi bachane ke zaroori aqdaam",
    guideCallHotline: "Qaumi Emergency: 112 / 911",
    guideDoTitle: "Fauran Kya Karain (Do's)",
    guideDontTitle: "Kin Cheezon Se Parhaiz Karain (Don'ts)",
    guideNotice: "RescuNet Hifazati Notice: Yeh hidayat sirf fauri salamti ke liye hain. Mauqa par mojood sarkari emergency amlay ki hidayat par sakhti se amal karain.",

    // Info Cards
    cardTriageTitle: "Munsifana AI Triage",
    cardTriageDesc: "Har report ka shiddat aur khatray ke hisab se jaiza liya jata hai taakay intehayi nazuk cases ko sab se pehle imdad mil sakay.",
    cardEdgeTitle: "Offline Edge Gateway",
    cardEdgeDesc: "Agar mobile network band bhi ho jaye, reports local edge gateway par mehfooz rehti hain aur rabta bahaal hotay hi sync ho jati hain.",
    cardApprovalTitle: "Insani Tasdeeq Lazmi Hai",
    cardApprovalDesc: "AI sirf tajweez banata hai, magar kisi bhi rescue team ki rawangi se pehle human coordinator tasdeeq karta hai.",

    // Footer
    footerDisclaimer: "RescuNet aik khud-mukhtar, AI-assisted emergency coordination project hai. Zindagi ko khatray ki soorat mein hamesha qaumi emergency services (112 / 911 / 15 / 1122) par call karain. Aam shehri doosray logon ki reports ya admin controls nahi dekh saktay.",
    footerRights: "RescuNet Emergency Coordination System • Tamam Reports Mehfooz Hain",
  },
};
