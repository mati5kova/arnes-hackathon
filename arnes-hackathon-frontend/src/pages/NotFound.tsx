import { useLanguage } from "@/lib/i18n";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const NotFound = () => {
	const location = useLocation();
	const { m } = useLanguage();

	useEffect(() => {
		console.error("404 Error: User attempted to access non-existent route:", location.pathname);
	}, [location.pathname]);

	return (
		<div className="flex min-h-screen items-center justify-center bg-muted">
			<div className="text-center">
				<h1 className="mb-4 text-4xl font-bold">404</h1>
				<p className="mb-4 text-xl text-muted-foreground">{m.notFound.title}</p>
				<a href="/" className="text-primary underline hover:text-primary/90">
					{m.notFound.backHome}
				</a>
			</div>
		</div>
	);
};

export default NotFound;
