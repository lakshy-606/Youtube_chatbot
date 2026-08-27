import {
  Cloud,
  Database,
  FileText,
  MapPin,
  Monitor,
  RefreshCw,
  Search,
  Server,
  Shield,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

// Component breakdown for the About page — kept as data so the page itself stays presentational.
export type ArchComponent = {
  icon: LucideIcon;
  name: string;
  tag: string;
  description: string;
};

export const ARCHITECTURE: ArchComponent[] = [
  {
    icon: Monitor,
    name: "Frontend",
    tag: "Next.js 16 · Vercel AI SDK",
    description:
      "The chat UI you're using right now — streaming responses via useChat, multi-session state, markdown rendering, this whole page.",
  },
  {
    icon: Server,
    name: "RAG Backend",
    tag: "FastAPI · Python",
    description:
      "A Python function deployed as a Vercel serverless function. Orchestrates retrieval, prompting, and streaming — no separate server to run.",
  },
  {
    icon: Sparkles,
    name: "Language model",
    tag: "Groq · gpt-oss-120b",
    description:
      "An open-weight model, hosted free by Groq. No OpenAI or Anthropic key anywhere in this stack — deliberately.",
  },
  {
    icon: Database,
    name: "Vector store",
    tag: "Pinecone",
    description:
      "Transcript chunks are embedded and stored per-video (namespaced by video ID), queried at ask-time. Embeddings themselves come from Pinecone's own hosted inference, not a separate provider.",
  },
  {
    icon: FileText,
    name: "Transcripts",
    tag: "Supadata",
    description:
      "YouTube transcripts fetched via a hosted API — chosen after discovering YouTube blocks scraping requests from cloud IPs, including Vercel's own.",
  },
  {
    icon: RefreshCw,
    name: "Conversational memory",
    tag: "Sliding-window STM",
    description:
      "The last few turns of a conversation are kept and used to rephrase follow-up questions into standalone ones before retrieval runs.",
  },
  {
    icon: MapPin,
    name: "Timestamp citations",
    tag: "Segment-aware chunking",
    description:
      "Transcript chunks are grouped at real segment boundaries, not arbitrary character cuts — so every citation links to an exact, correct moment in the video.",
  },
  {
    icon: Cloud,
    name: "Deployment",
    tag: "Vercel · Hobby (free)",
    description:
      "Frontend and backend deploy together as one project on Vercel's free tier — no separate hosting, no credit card.",
  },
];

export const ROADMAP: ArchComponent[] = [
  {
    icon: Search,
    name: "Advanced retrieval",
    tag: "In progress",
    description: "Hybrid dense+sparse search, multi-query expansion, and reranking — all Pinecone-hosted, no heavy local models.",
  },
  {
    icon: Shield,
    name: "Guardrails",
    tag: "Planned",
    description: "LLM-based input/output validation via Guardrails AI — prompt-injection detection, groundedness checks, and more.",
  },
  {
    icon: Sparkles,
    name: "Evaluation suite",
    tag: "Planned",
    description: "DeepEval-based scoring: precision, recall, faithfulness, answer relevance, the RAG triad, and G-Eval correctness/completeness.",
  },
];
