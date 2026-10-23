import axiosInstance from 'axios';
import GlassPane from "../../components/GlassPane";
import InputSection from "../../components/InputSection";
import ButtonPrimary from "../../components/ButtonPrimary";
import ButtonInline from "../../components/ButtonInline";
import { apiClient } from "../../services/apiClient";
import { useState } from "react";

function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError('');
        try {
            //const response = await  apiClient.post('/auth/login', { email, password });

            // if (response.data.success) {
            //     const token = response.data.data.token;
            //     const userData = response.data.data.user;

            //     login(token, userData);
            //         navigate('/');
            // } else {
            //     setError(response.data.message || 'Niepoprawne dane logowania.');
            // }
            await new Promise((resolve) => setTimeout(resolve, 500));
            const mockToken = "fake-jwt-token-12345";
            const mockUser = {
                id: "1",
                email: email || "test@neurotrace.com",
                role: "admin" as const, // lub 'admin' w zależności od tego, co chcesz testować
                firstName: "Jan",
                lastName: "Kowalski",
                createdAt: new Date().toISOString(),
            };
            login(mockToken, mockUser as any);
            navigate('/');

        } catch (err: unknown) {
            if (axiosInstance.isAxiosError(err)) {
                const backendMessage = err.response?.data?.message;
                setError(backendMessage || 'Niepoprawny e-mail lub hasło.');
            } else {
                setError('Błąd połączenia z serwerem. Upewnij się, że backend działa.');
            }
        }
    }
    return (
        <GlassPane className="flex min-h-[490px] w-full max-w-[342px] flex-col items-stretch px-[33px] pb-[30px] pt-[38px]">
            <div className="flex h-11 items-center justify-center gap-1.5" aria-label="NeuroTrace">
                <img className="h-11 w-11 object-contain" src="/favicon-light.svg" alt="" />
                <span className="font-heading text-[30px] font-extrabold leading-none tracking-[-0.7px]">
                    <span className="text-[#00877f]">Neuro</span>
                    <span className="text-[#00425c]">Trace</span>
                </span>
            </div>

            <h1 className="mt-[55px] text-center font-heading text-[36px] font-extrabold leading-[1.15] tracking-[-0.4px] text-[#06234e]">
                SIGN IN
            </h1>

            <form
                className="mt-[48px] flex flex-col gap-[18px]"
                onSubmit={handleLogin}
            >
                <InputSection
                    label="Email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    placeholder="Email address"
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
                <InputSection
                    label="Password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="Password"
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
                <ButtonPrimary type="submit">SIGN IN</ButtonPrimary>
                <ButtonInline type="button">Forgot password?</ButtonInline>
            </form>
        </GlassPane>
    );
}
import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default LoginPage;
