export type ModuleKey = "chat" | "case" | "research" | "draft" | "contract" | "evidence" | "fir" | "strength";

export const modules: Record<ModuleKey, { title: string; description: string; actionLabel: string }> = {
  chat: {
    title: "AI Legal Chatbot",
    description: "Ask legal questions and get RAG-grounded answers with citations from statutes and case passages.",
    actionLabel: "Ask NyayaSetu",
  },
  case: {
    title: "Case Analysis Engine",
    description: "Map incident facts to likely laws, evidence requirements, punishment context, and next steps.",
    actionLabel: "Analyze Case",
  },
  research: {
    title: "Legal Research Engine",
    description: "Search bare acts, statutes, and legal passages through semantic retrieval.",
    actionLabel: "Run Research",
  },
  draft: {
    title: "Legal Document Drafting",
    description: "Generate notices, complaints, affidavits, and structured legal drafts for review.",
    actionLabel: "Generate Draft",
  },
  contract: {
    title: "Contract Analysis",
    description: "Review contracts for clause extraction, risks, and missing protections.",
    actionLabel: "Analyze Contract",
  },
  evidence: {
    title: "Evidence Analyzer",
    description: "Extract text, entities, and timeline clues from uploaded or pasted evidence.",
    actionLabel: "Analyze Evidence",
  },
  fir: {
    title: "FIR Generator",
    description: "Prepare editable FIR drafts from manual entry, complaint uploads, and voice input.",
    actionLabel: "Open FIR Workspace",
  },
  strength: {
    title: "Case Strength Prediction",
    description: "Estimate the readiness of a case based on evidence, witness support, and procedure.",
    actionLabel: "Score Case Strength",
  },
};

export const moduleOrder: ModuleKey[] = ["chat", "case", "research", "draft", "contract", "evidence", "fir", "strength"];

export const rightRailPrompts = [
  "Explain BNS theft in simple language.",
  "Draft a legal notice for non-payment.",
  "Analyze a cyber fraud complaint.",
  "Summarize a Supreme Court bail judgment.",
  "Review a rental agreement for missing clauses.",
  "Prepare an FIR draft for mobile theft.",
];

export const quickLinks = [
  "AI Legal Chatbot",
  "Case Analysis Engine",
  "Legal Research Engine",
  "Legal Document Drafting",
  "Contract Analysis",
  "Evidence Analyzer",
  "FIR Generator",
  "Case Strength Prediction",
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
    title: "RAG-Powered Legal Guidance",
    description: "Every answer is tied to retrieved legal materials instead of unsupported free-text generation.",
    tone: "blue",
  },
  {
    title: "Citizen and Police Workflows",
    description: "Support FIR drafting, case intake, evidence review, and legal research in one platform.",
    tone: "purple",
  },
  {
    title: "Self-Hosted AI Stack",
    description: "Use open-source models, FAISS retrieval, FastAPI services, and local document pipelines.",
    tone: "green",
  },
  {
    title: "Editable Legal Previews",
    description: "Render readable outputs with download-ready previews instead of raw JSON payloads.",
    tone: "amber",
  },
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
