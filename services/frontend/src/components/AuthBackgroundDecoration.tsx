import ellipseUrl from "../assets/deco-ellipse.svg";

function AuthBackgroundDecoration() {
    return (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
            <img
                className="absolute left-1/2 top-1/2 h-auto w-1292px max-w-none -translate-x-1/2 -translate-y-1/2 scale-[0.80]"
                src={ellipseUrl}
                alt=""
            />
            <img
                className="absolute left-1/2 top-1/2 h-auto w-1292px max-w-none -translate-x-2/5 -translate-y-4/9 rotate-[305deg] scale-x-[0.6] scale-y-50"
                src={ellipseUrl}
                alt=""
            />
        </div>
    );
}

export default AuthBackgroundDecoration;