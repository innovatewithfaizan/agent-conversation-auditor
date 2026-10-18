import { marked } from "marked";
import { fetchPolicy } from "../data";
import { Loading, useLoad } from "../components/ui";

export default function PolicyPage() {
  const [policy, error] = useLoad(fetchPolicy);
  if (!policy) return <Loading error={error} />;
  // The policy is our own Markdown file from the repository, not user input.
  const html = marked.parse(policy.text, { async: false }) as string;
  return <article className="card prose" dangerouslySetInnerHTML={{ __html: html }} />;
}
