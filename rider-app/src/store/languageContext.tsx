import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { storage } from '../utils/storage';

export type Language = 'en' | 'hi' | 'mr';

// Translation Dictionary
export const translations = {
  en: {
    // Navigation & Headers
    home: 'Home',
    history: 'History',
    profile: 'Profile',
    settings: 'Settings',
    
    // Home Screen
    readyToRide: 'Ready to Ride',
    readyAndProtected: 'Ready & Protected',
    startShift: 'Start Shift',
    dashboard: 'Dashboard',
    walletBalance: 'WALLET BALANCE',
    recharge: 'Recharge',
    activeProtection: 'Active Protection',
    protectionDetails: 'Protection Details',
    personalAccidentMedical: 'Personal Accident & Medical',
    activeShift: 'Active Shift',
    todaysShift: "Today's Shift",
    dailyInsight: 'Daily Insight',
    wetRoadsInsight: 'Wet roads reported downtown. Reduce speed by 15% and increase braking distance to maintain optimal safety ratings today.',
    medicalCoverageDesc: 'Medical bill coverage up to ₹1,00,000 for injuries sustained during shifts.',
    medicalCoverageActiveDesc: 'Medical bills and hospitalization expense coverage up to ₹50,000.',
    
    // Settings Screen
    appPreferences: 'App Preferences',
    pushNotifications: 'Push Notifications',
    autoStartShift: 'Auto-start shift (mock)',
    autoStartDesc: 'Start shift automatically when moving.',
    offlineMode: 'Offline mode sync',
    offlineModeDesc: 'Sync telemetry later if offline.',
    devicePermissions: 'Device Permissions',
    locationServices: 'Location Services',
    motionSensors: 'Motion Sensors',
    accountSecurity: 'Account & Security',
    changePassword: 'Change Password',
    emergencyContacts: 'Emergency Contacts',
    logOut: 'Log Out',
    appLanguage: 'App Language',
    selectLanguage: 'Select Language',
    granted: 'Granted',
    set: 'set',
    
    // Profile Screen
    riderInformation: 'Rider Information',
    vehicleAndRegistration: 'Vehicle & Registration',
    vehicleType: 'Vehicle Type',
    makeAndModel: 'Make & Model',
    licensePlate: 'License Plate',
    settingsAndPreferences: 'Settings & Preferences',
    privacyAndSecurity: 'Privacy & Security',
    language: 'Language',
    risk: 'Risk',
    approved: 'APPROVED',
    pending: 'PENDING',
    rejected: 'REJECTED',
    live: 'LIVE',
    twoWheeler: 'Two Wheeler (Bike/Scooter)',
    threeWheeler: 'Three Wheeler (Auto)',
    fourWheeler: 'Four Wheeler (Cab/Taxi)',
    bicycle: 'Bicycle',
    notifications: 'Notifications',
    
    // Live Ride Screen
    liveRide: 'Live Ride',
    statusActive: 'ACTIVE',
    statusPaused: 'PAUSED',
    endShift: 'End Shift',
    currentSpeed: 'Current Speed',
    safetyScore: 'Safety Score',
    premiumRate: 'Premium Rate',
    hardBraking: 'Hard Braking',
    overspeeding: 'Overspeeding',
    kmh: 'km/h',
    perKm: '/ km',
    events: 'Events',
    
    // Helmet Check
    helmetVerification: 'Helmet Verification',
    putOnHelmet: 'Please wear your helmet to verify safety before starting the shift.',
    confirmHelmetWorn: 'I confirm my helmet is worn correctly',
    verifyAndStart: 'Verify & Start Shift',
    verifying: 'Verifying...',
    
    // Crash Alert
    crashDetected: 'Crash Detected!',
    areYouOkay: 'Are you okay?',
    respondingIn: 'Responding in 10 seconds...',
    triggerSos: 'Trigger SOS Now',
    iAmOkay: 'I am Okay',
    dismissAlert: 'Dismiss Alert',
    
    // SOS Screen
    sosTriggered: 'SOS Emergency Triggered',
    contactsNotified: 'Emergency contacts and closest ambulance have been notified.',
    dispatchingHelp: 'Dispatching help to your location...',
    cancelSos: 'Cancel SOS'
  },
  hi: {
    // Navigation & Headers
    home: 'होम',
    history: 'इतिहास',
    profile: 'प्रोफ़ाइल',
    settings: 'सेटिंग्स',
    
    // Home Screen
    readyToRide: 'सवारी के लिए तैयार',
    readyAndProtected: 'तैयार और सुरक्षित',
    startShift: 'शिफ्ट शुरू करें',
    dashboard: 'डैशबोर्ड',
    walletBalance: 'वॉलेट बैलेंस',
    recharge: 'रिचार्ज',
    activeProtection: 'सक्रिय सुरक्षा',
    protectionDetails: 'सुरक्षा विवरण',
    personalAccidentMedical: 'व्यक्तिगत दुर्घटना और चिकित्सा',
    activeShift: 'सक्रिय शिफ्ट',
    todaysShift: "आज की शिफ्ट",
    dailyInsight: 'दैनिक अंतर्दृष्टि',
    wetRoadsInsight: 'शहर में गीली सड़कों की सूचना है। आज इष्टतम सुरक्षा रेटिंग बनाए रखने के लिए गति में 15% की कमी करें और ब्रेकिंग दूरी बढ़ाएं।',
    medicalCoverageDesc: 'शिफ्ट के दौरान लगी चोटों के लिए ₹1,00,000 तक का चिकित्सा बिल कवर।',
    medicalCoverageActiveDesc: '₹50,000 तक का मेडिकल बिल और अस्पताल में भर्ती होने का खर्च कवर।',
    
    // Settings Screen
    appPreferences: 'ऐप प्राथमिकताएं',
    pushNotifications: 'पुश सूचनाएं',
    autoStartShift: 'ऑटो-स्टार्ट शिफ्ट (मॉक)',
    autoStartDesc: 'चलने पर स्वचालित रूप से शिफ्ट शुरू करें।',
    offlineMode: 'ऑफलाइन मोड सिंक',
    offlineModeDesc: 'ऑफलाइन होने पर टेलीमेट्री बाद में सिंक करें।',
    devicePermissions: 'डिवाइस अनुमतियां',
    locationServices: 'स्थान सेवाएं',
    motionSensors: 'मोशन सेंसर',
    accountSecurity: 'खाता और सुरक्षा',
    changePassword: 'पासवर्ड बदलें',
    emergencyContacts: 'आपातकालीन संपर्क',
    logOut: 'लॉग आउट',
    appLanguage: 'ऐप की भाषा',
    selectLanguage: 'भाषा चुनें',
    granted: 'स्वीकृत',
    set: 'सेट',
    
    // Profile Screen
    riderInformation: 'राइडर जानकारी',
    vehicleAndRegistration: 'वाहन और पंजीकरण',
    vehicleType: 'वाहन का प्रकार',
    makeAndModel: 'मेक और मॉडल',
    licensePlate: 'लायसेंस प्लेट',
    settingsAndPreferences: 'सेटिंग्स और प्राथमिकताएं',
    privacyAndSecurity: 'गोपनीयता और सुरक्षा',
    language: 'भाषा',
    risk: 'जोखिम',
    approved: 'स्वीकृत',
    pending: 'लंबित',
    rejected: 'अस्वीकृत',
    live: 'लाइव',
    twoWheeler: 'दो पहिया (बाइक/स्कूटर)',
    threeWheeler: 'तीन पहिया (ऑटो)',
    fourWheeler: 'चार पहिया (कैब/टैक्सी)',
    bicycle: 'साइकिल',
    notifications: 'सूचनाएं',
    
    // Live Ride Screen
    liveRide: 'सक्रिय सवारी',
    statusActive: 'सक्रिय',
    statusPaused: 'रुका हुआ',
    endShift: 'शिफ्ट समाप्त करें',
    currentSpeed: 'वर्तमान गति',
    safetyScore: 'सुरक्षा स्कोर',
    premiumRate: 'प्रीमियम दर',
    hardBraking: 'अचानक ब्रेक',
    overspeeding: 'तेज गति',
    kmh: 'किमी/घंटा',
    perKm: '/ किमी',
    events: 'घटनाएं',
    
    // Helmet Check
    helmetVerification: 'हेलमेट सत्यापन',
    putOnHelmet: 'शिफ्ट शुरू करने से पहले सुरक्षा सत्यापित करने के लिए कृपया अपना हेलमेट पहनें।',
    confirmHelmetWorn: 'मैं पुष्टि करता हूं कि मेरा हेलमेट सही ढंग से पहना गया है',
    verifyAndStart: 'सत्यापित करें और शिफ्ट शुरू करें',
    verifying: 'सत्यापन हो रहा है...',
    
    // Crash Alert
    crashDetected: 'दुर्घटना का पता चला!',
    areYouOkay: 'क्या आप ठीक हैं?',
    respondingIn: '10 सेकंड में प्रतिक्रिया...',
    triggerSos: 'एसओएस अभी ट्रिगर करें',
    iAmOkay: 'मैं ठीक हूँ',
    dismissAlert: 'अलर्ट खारिज करें',
    
    // SOS Screen
    sosTriggered: 'एसओएस आपातकाल ट्रिगर हुआ',
    contactsNotified: 'आपातकालीन संपर्कों और निकटतम एम्बुलेंस को सूचित कर दिया गया है।',
    dispatchingHelp: 'आपके स्थान पर सहायता भेजी जा रही है...',
    cancelSos: 'एसओएस रद्द करें'
  },
  mr: {
    // Navigation & Headers
    home: 'होम',
    history: 'इतिहास',
    profile: 'प्रोफाईल',
    settings: 'सेटिंग्ज',
    
    // Home Screen
    readyToRide: 'प्रवासासाठी तयार',
    readyAndProtected: 'तयार आणि सुरक्षित',
    startShift: 'शिफ्ट सुरू करा',
    dashboard: 'डॅशबोर्ड',
    walletBalance: 'वॉलेट शिल्लक',
    recharge: 'रिचार्ज',
    activeProtection: 'सक्रिय संरक्षण',
    protectionDetails: 'संरक्षण तपशील',
    personalAccidentMedical: 'वैयक्तिक अपघात आणि वैद्यकीय',
    activeShift: 'सक्रिय शिफ्ट',
    todaysShift: "आजची शिफ्ट",
    dailyInsight: 'दैनिक अंतर्दृष्टी',
    wetRoadsInsight: 'शहरात ओल्या रस्त्यांची नोंद झाली आहे. आज सर्वोत्तम सुरक्षा रेटिंग राखण्यासाठी वेग १५% कमी करा आणि ब्रेकिंगचे अंतर वाढवा.',
    medicalCoverageDesc: 'शिफ्ट दरम्यान झालेल्या दुखापतींसाठी ₹१,००,००० पर्यंतचे वैद्यकीय बिल संरक्षण.',
    medicalCoverageActiveDesc: '₹५०,००० पर्यंतचे वैद्यकीय बिल आणि रुग्णालयात दाखल करण्याचा खर्च संरक्षण.',
    
    // Settings Screen
    appPreferences: 'अॅप प्राधान्ये',
    pushNotifications: 'पुश सूचना',
    autoStartShift: 'ऑटो-स्टार्ट शिफ्ट (मॉक)',
    autoStartDesc: 'चालू असताना स्वयंचलितपणे शिफ्ट सुरू करा.',
    offlineMode: 'ऑफलाइन मोड सिंक',
    offlineModeDesc: 'ऑफलाइन असल्यास टेलीमेट्री नंतर सिंक करा.',
    devicePermissions: 'डिव्हाइस परवानग्या',
    locationServices: 'स्थान सेवा',
    motionSensors: 'मोशन सेन्सर्स',
    accountSecurity: 'खाते आणि सुरक्षा',
    changePassword: 'पासवर्ड बदला',
    emergencyContacts: 'आपत्कालीन संपर्क',
    logOut: 'लॉग आउट',
    appLanguage: 'अॅपची भाषा',
    selectLanguage: 'भाषा निवडा',
    granted: 'मंजूर',
    set: 'सेट',
    
    // Profile Screen
    riderInformation: 'रायडर माहिती',
    vehicleAndRegistration: 'वाहन आणि नोंदणी',
    vehicleType: 'वाहनाचा प्रकार',
    makeAndModel: 'मेक आणि मॉडेल',
    licensePlate: 'लायसन्स प्लेट',
    settingsAndPreferences: 'सेटिंग्ज आणि प्राधान्ये',
    privacyAndSecurity: 'गोपनीयता आणि सुरक्षा',
    language: 'भाषा',
    risk: 'धोका',
    approved: 'मंजूर',
    pending: 'प्रलंबित',
    rejected: 'नाकारले',
    live: 'लाइव्ह',
    twoWheeler: 'दुचाकी (बाइक/स्कूटर)',
    threeWheeler: 'तिचाकी (ऑटो)',
    fourWheeler: 'चारचाकी (कॅब/टैक्सी)',
    bicycle: 'सायकल',
    notifications: 'सूचना',
    
    // Live Ride Screen
    liveRide: 'थेट प्रवास',
    statusActive: 'सक्रिय',
    statusPaused: 'थांबवले',
    endShift: 'शिफ्ट संपवा',
    currentSpeed: 'सध्याचा वेग',
    safetyScore: 'सुरक्षा गुण',
    premiumRate: 'प्रीमियम दर',
    hardBraking: 'अचानक ब्रेक',
    overspeeding: 'अतिवेग',
    kmh: 'किमी/तास',
    perKm: '/ किमी',
    events: 'घटना',
    
    // Helmet Check
    helmetVerification: 'हेलमेट पडताळणी',
    putOnHelmet: 'शिफ्ट सुरू करण्यापूर्वी सुरक्षा पडताळण्यासाठी कृपया आपले हेलमेट घाला.',
    confirmHelmetWorn: 'मी पुष्टी करतो की माझे हेलमेट योग्यरित्या घातले आहे',
    verifyAndStart: 'पडताळणी करा आणि शिफ्ट सुरू करा',
    verifying: 'पडताळणी करत आहे...',
    
    // Crash Alert
    crashDetected: 'अपघात आढळला!',
    areYouOkay: 'तुम्ही ठीक आहात का?',
    respondingIn: '१० सेकंदात प्रतिसाद...',
    triggerSos: 'एसओएस आत्ताच ट्रिगर करा',
    iAmOkay: 'मी ठीक आहे',
    dismissAlert: 'अलर्ट बंद करा',
    
    // SOS Screen
    sosTriggered: 'एसओएस आणीबाणी ट्रिगर झाली',
    contactsNotified: 'आपत्कालीन संपर्क आणि जवळच्या रुग्णवाहिकेला सूचित करण्यात आले आहे.',
    dispatchingHelp: 'तुमच्या स्थानावर मदत पाठवली जात आहे...',
    cancelSos: 'एसओएस रद्द करा'
  }
};

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => Promise<void>;
  t: (key: keyof typeof translations['en']) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const LANGUAGE_STORAGE_KEY = 'rideshield_app_language';

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>('en');

  // Load language preference from storage on mount
  useEffect(() => {
    async function loadSavedLanguage() {
      const savedLang = await storage.getItem(LANGUAGE_STORAGE_KEY);
      if (savedLang === 'en' || savedLang === 'hi' || savedLang === 'mr') {
        setLanguageState(savedLang);
      }
    }
    loadSavedLanguage();
  }, []);

  const setLanguage = async (lang: Language) => {
    setLanguageState(lang);
    await storage.setItem(LANGUAGE_STORAGE_KEY, lang);
  };

  const t = (key: keyof typeof translations['en']): string => {
    const langDict = translations[language] || translations['en'];
    return langDict[key] || translations['en'][key] || String(key);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
