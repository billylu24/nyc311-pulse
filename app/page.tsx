import { Dashboard } from "@/components/dashboard";
import { staticSnapshot } from "@/lib/static-snapshot";

export default function Home() { return <Dashboard initial={staticSnapshot} />; }
