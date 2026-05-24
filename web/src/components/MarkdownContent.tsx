import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./MarkdownContent.css";

type MarkdownContentProps = {
  content: string;
  className?: string;
};

export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  if (!content.trim()) return null;

  return (
    <div className={`markdown-content ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
