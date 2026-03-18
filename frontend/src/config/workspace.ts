export type ModuleKey = "chat" | "case" | "research" | "draft" | "contract" | "evidence" | "fir" | "strength";

export const modules: Record<ModuleKey, { title: string; description: string; actionLabel: string }> = {
  chat: {
    title: "AI Legal Assistant",
    description: "Ask legal questions in plain language and get grounded guidance with statutory citations and next steps.",
    actionLabel: "Ask Legal Assistant",
  },
  case: {
    title: "Case Analysis",
    description: "Turn incident facts into possible BNS or IPC sections, reasoning, likely charges, and recommended actions.",
    actionLabel: "Analyze My Case",
  },
  research: {
    title: "Bare Acts & Legal Knowledge Base",
    description: "Search BNS, BNSS, IPC, judgments, and legal passages through semantic retrieval and official citations.",
    actionLabel: "Search Legal Knowledge",
  },
  draft: {
    title: "Complaint & Legal Drafting",
    description: "Convert citizen issues into legal complaints, notices, and formal drafts that can be reviewed and edited.",
    actionLabel: "Generate Complaint Draft",
  },
  contract: {
    title: "Legal Vault",
    description: "Review contracts, store legal documents, and inspect clause-level risk with a lawyer-ready preview.",
    actionLabel: "Open Legal Vault",
  },
  evidence: {
    title: "Complaint Upload & OCR",
    description: "Upload complaint images, PDFs, or evidence files and extract structured text, entities, and timelines.",
    actionLabel: "Analyze Uploaded Evidence",
  },
  fir: {
    title: "File Complaint & Voice FIR",
    description: "Draft editable FIRs from manual forms, uploaded complaints, or voice narration for police review.",
    actionLabel: "Open Complaint Workspace",
  },
  strength: {
    title: "Track Case & Case Strength",
    description: "Estimate case readiness and track investigation quality using evidence, witness support, and procedure.",
    actionLabel: "Evaluate Case Readiness",
  },
};

export const moduleOrder: ModuleKey[] = ["chat", "fir", "case", "research", "draft", "evidence", "contract", "strength"];

export const platformNavigation = [
  { label: "Home", section: "hero" },
  { label: "AI Legal Assistant", module: "chat" as ModuleKey, section: "workspace" },
  { label: "File Complaint", module: "fir" as ModuleKey, section: "workspace" },
  { label: "Voice FIR", module: "fir" as ModuleKey, section: "workspace" },
  { label: "Case Analysis", module: "case" as ModuleKey, section: "workspace" },
  { label: "Find Lawyers", section: "lawyer-marketplace" },
  { label: "Lawyer Network", section: "lawyer-network" },
  { label: "Bare Acts", module: "research" as ModuleKey, section: "workspace" },
  { label: "Legal Vault", module: "contract" as ModuleKey, section: "workspace" },
  { label: "Track Case", module: "strength" as ModuleKey, section: "workspace" },
] as const;

export const rightRailPrompts = [
  "My landlord is refusing to return my deposit.",
  "Draft a complaint for cyber fraud and OTP theft.",
  "Explain BNS theft in simple language.",
  "Summarize a Supreme Court bail judgment.",
  "Prepare a voice FIR for phone theft near a market.",
  "Find a criminal lawyer in Delhi with 8 years experience.",
];

export const quickLinks = [
  "Citizens",
  "Police",
  "Verified Lawyers",
  "Lawyer Network",
  "Voice FIR",
  "OCR Complaints",
  "Bare Acts",
  "Legal Vault",
];

export const samplePrompts: Record<Exclude<ModuleKey, "fir">, string[]> = {
  chat: [
    "What should be included in an FIR for phone theft?",
    "Can police refuse to register an FIR in India?",
    "Explain criminal intimidation under BNS.",
  ],
  case: [
    "Analyze a cyber fraud complaint with bank SMS and call logs.",
    "Map assault allegations to applicable sections and evidence needs.",
    "Review an extortion threat complaint sent over WhatsApp.",
  ],
  research: [
    "criminal intimidation for online threats",
    "tenant rights and eviction procedure in India",
    "electronic evidence certificate under Section 65B",
  ],
  draft: [
    "Draft a legal notice for delayed refund.",
    "Create an NDA for a startup partnership.",
    "Prepare a consumer complaint for defective goods.",
  ],
  contract: [
    "Review a rental agreement for missing termination clauses.",
    "Analyze an NDA for uncapped indemnity risk.",
    "Check a service agreement for governing law and dispute resolution.",
  ],
  evidence: [
    "Extract timeline and entities from complaint screenshots.",
    "Analyze a bank fraud transcript.",
    "Review a PDF evidence file for key dates and identities.",
  ],
  strength: [
    "Estimate readiness when there are screenshots and one witness.",
    "Check a delayed complaint with no documents.",
    "Score a case with strong evidence and matching jurisdiction.",
  ],
};

export const exploreCards = [
  {
    title: "AI Complaint Assistant",
    description: "Describe a legal problem in simple language and turn it into a structured complaint or FIR-ready narrative.",
    tone: "navy",
  },
  {
    title: "Voice FIR Filing",
    description: "Narrate a complaint naturally and let NyayaSetu convert it into an editable FIR draft for review.",
    tone: "gold",
  },
  {
    title: "Case Analysis Engine",
    description: "Map incident facts to possible IPC or BNS sections, legal reasoning, likely charges, and next steps.",
    tone: "stone",
  },
  {
    title: "Complaint Upload with OCR",
    description: "Upload complaint images or PDFs and extract structured legal fields through OCR and document analysis.",
    tone: "platinum",
  },
  {
    title: "Crime Pattern Detection",
    description: "Track repeated crimes by location, incident type, and historical FIR records to surface hotspots.",
    tone: "navy",
  },
  {
    title: "Legal Knowledge Base",
    description: "Search bare acts, BNS, BNSS, IPC, and important judgments with grounded, simple-language explanations.",
    tone: "gold",
  },
] as const;

export const lawyerProfiles = [
  {
    name: "Advocate Ananya Sharma",
    handle: "@adv_sharma",
    practice: "Criminal Law",
    court: "Delhi High Court",
    experience: "8 years",
    location: "New Delhi",
    rating: "4.9",
    fee: "INR 2,500",
  },
  {
    name: "Advocate Rohan Mehta",
    handle: "@justice_rohan",
    practice: "Cyber Crime",
    court: "Mumbai Sessions Court",
    experience: "11 years",
    location: "Mumbai",
    rating: "4.8",
    fee: "INR 3,000",
  },
  {
    name: "Advocate Saba Khan",
    handle: "@legal_saba",
    practice: "Family & Property",
    court: "Lucknow Bench",
    experience: "6 years",
    location: "Lucknow",
    rating: "4.7",
    fee: "INR 1,800",
  },
] as const;

export const lawyerNetworkFeed = [
  {
    author: "Advocate Ananya Sharma",
    handle: "@adv_sharma",
    category: "Judgment Insight",
    title: "How courts are reading digital evidence in recent criminal proceedings",
    excerpt: "A short breakdown of what makes screenshots, call records, and recovery memos persuasive during early-stage criminal investigation.",
    stats: "128 likes · 24 comments",
  },
  {
    author: "Advocate Rohan Mehta",
    handle: "@justice_rohan",
    category: "Citizen Q&A",
    title: "What should a victim preserve after OTP fraud?",
    excerpt: "The practical answer is not only bank statements. Preserve the call log, complaint number, device details, and communication chain immediately.",
    stats: "94 likes · 17 comments",
  },
  {
    author: "Advocate Saba Khan",
    handle: "@legal_saba",
    category: "Bare Act Thread",
    title: "Tenant deposit disputes: when negotiation should end and legal notice should begin",
    excerpt: "A practical thread on using documentary trail, timelines, and jurisdiction before escalating to formal complaint drafting.",
    stats: "73 likes · 11 comments",
  },
] as const;

export const policeDashboardCards = [
  {
    title: "Complaint Review Queue",
    value: "26 pending",
    detail: "OCR-normalized complaints waiting for station-level verification.",
  },
  {
    title: "Voice FIR Drafts",
    value: "11 generated",
    detail: "Citizen voice complaints converted into FIR-ready structured drafts.",
  },
  {
    title: "Hotspot Signals",
    value: "3 active zones",
    detail: "Repeated theft and intimidation patterns detected in the last 7 days.",
  },
] as const;

export const citizenAssistantHighlights = [
  "Possible legal provisions",
  "Suggested actions",
  "Draft complaint",
  "Recommended lawyers",
] as const;

export function fillCasePreset(preset: string) {
  if (preset.includes("cyber fraud")) {
    return {
      incident_description: "A caller impersonating a bank officer tricked me into sharing OTP details and money was withdrawn from my account.",
      location: "Lucknow",
      incident_date: "2026-03-09",
      people_involved: "Complainant, Unknown caller",
      evidence: "Call recording, bank SMS, transaction statement",
    };
  }
  if (preset.includes("assault")) {
    return {
      incident_description: "A neighbour assaulted me during a property dispute and I suffered visible injuries.",
      location: "Jaipur",
      incident_date: "2026-03-05",
      people_involved: "Complainant, Neighbour",
      evidence: "Medical report, witness statement, photos",
    };
  }
  return {
    incident_description: "A person sent repeated WhatsApp threats demanding money and threatening harm if payment was not made.",
    location: "Bengaluru",
    incident_date: "2026-03-01",
    people_involved: "Complainant, Unknown sender",
    evidence: "WhatsApp screenshots, call logs, payment demand message",
  };
}

export function fillDraftPreset(preset: string) {
  if (preset.includes("NDA")) {
    return {
      draft_type: "nda",
      facts: "Two business partners want to exchange confidential product and customer information during due diligence.",
      parties: "Founder A, Founder B",
      relief_sought: "Mutual confidentiality obligations and restricted disclosure",
      jurisdiction: "New Delhi",
    };
  }
  if (preset.includes("consumer")) {
    return {
      draft_type: "consumer complaint",
      facts: "A defective product was delivered and the seller refused replacement or refund despite repeated requests.",
      parties: "Consumer, Seller",
      relief_sought: "Refund, replacement, and compensation",
      jurisdiction: "Lucknow",
    };
  }
  return {
    draft_type: "legal notice",
    facts: "The buyer paid the full amount but the seller never delivered the goods or refunded the money.",
    parties: "Buyer, Seller",
    relief_sought: "Refund with interest and compensation",
    jurisdiction: "Bengaluru",
  };
}

export function fillStrengthPreset(preset: string) {
  if (preset.includes("no documents")) {
    return {
      evidence_items: 0,
      witness_count: 0,
      documentary_support: false,
      police_complaint_filed: false,
      incident_recency_days: 75,
      jurisdiction_match: true,
    };
  }
  if (preset.includes("strong evidence")) {
    return {
      evidence_items: 5,
      witness_count: 2,
      documentary_support: true,
      police_complaint_filed: true,
      incident_recency_days: 2,
      jurisdiction_match: true,
    };
  }
  return {
    evidence_items: 3,
    witness_count: 1,
    documentary_support: true,
    police_complaint_filed: false,
    incident_recency_days: 5,
    jurisdiction_match: true,
  };
}
