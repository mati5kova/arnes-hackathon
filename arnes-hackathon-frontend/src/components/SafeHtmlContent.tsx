import DOMPurify from "dompurify";
import parse, { domToReact, Element, type HTMLReactParserOptions } from "html-react-parser";

const HTML_TAG_PATTERN = /<\/?[a-z][\s\S]*>/i;
const ALLOWED_TAGS = ["a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "li", "ol", "p", "pre", "strong", "ul"];

interface SafeHtmlContentProps {
	content: string;
}

const SafeHtmlContent = ({ content }: SafeHtmlContentProps) => {
	if (!HTML_TAG_PATTERN.test(content)) {
		return <p className="whitespace-pre-wrap break-words">{content}</p>;
	}

	const options: HTMLReactParserOptions = {
		replace(domNode) {
			if (!(domNode instanceof Element) || domNode.name !== "a") {
				return undefined;
			}

			const href = domNode.attribs.href;
			const childContent = domToReact(
				domNode.children as unknown as Parameters<typeof domToReact>[0],
				options,
			);
			if (!href) {
				return <>{childContent}</>;
			}

			return (
				<a href={href} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2">
					{childContent}
				</a>
			);
		},
	};

	const sanitizedHtml = DOMPurify.sanitize(content, {
		ALLOWED_TAGS,
		ALLOWED_ATTR: ["href", "title"],
	});

	return (
		<div className="break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_code]:rounded [&_code]:bg-background/80 [&_code]:px-1 [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_li+li]:mt-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p+p]:mt-3 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-background/80 [&_pre]:p-3 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5">
			{parse(sanitizedHtml, options)}
		</div>
	);
};

export default SafeHtmlContent;
