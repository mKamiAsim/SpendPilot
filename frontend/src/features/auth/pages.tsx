import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { useSession } from "../../app/session";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ApiRequestError, api, readJson, rememberCsrf } from "../../lib/api";
import { AuthLayout, FieldError } from "./AuthLayout";

const password = z.string().min(12, "Use at least 12 characters.").max(128);

const registerSchema = z.object({
  username: z.string().regex(/^[A-Za-z0-9_]{3,32}$/, "Use 3–32 letters, numbers, or underscores."),
  email: z.string().email("Enter a valid email address."),
  password,
});

const loginSchema = z.object({
  username: z.string().min(1, "Enter your username or email."),
  password: z.string().min(1, "Enter your password."),
});

function deliveryNote(mode: string) {
  if (mode === "captured") {
    return "A verification message was stored by the test mailer. That is not a live mailbox.";
  }
  if (mode === "sent") return "A verification link was sent.";
  return "Email delivery is not configured, so the verification link cannot be sent until SMTP is set.";
}

export function LoginPage() {
  const navigate = useNavigate();
  const { refresh } = useSession();
  const [formError, setFormError] = useState("");
  const form = useForm({ resolver: zodResolver(loginSchema), defaultValues: { username: "", password: "" } });

  return (
    <AuthLayout
      title="Sign in"
      footer={
        <p>
          New here? <Link to="/register">Create an account</Link>
        </p>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit(async (values) => {
          setFormError("");
          try {
            const response = await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify(values) });
            const body = await readJson<{ csrf_token: string }>(response);
            rememberCsrf(body.csrf_token);
            await refresh();
            navigate("/overview");
          } catch (error) {
            setFormError(error instanceof ApiRequestError ? error.message : "Sign-in failed.");
          }
        })}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="username">Username or email</Label>
          <Input id="username" autoComplete="username" {...form.register("username")} />
          <FieldError message={form.formState.errors.username?.message} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        <FieldError message={formError} />
        <Button type="submit">Sign in</Button>
        <Link to="/forgot" className="text-sm text-ink-secondary">
          Forgot password
        </Link>
      </form>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { refresh } = useSession();
  const [formError, setFormError] = useState("");
  const [note, setNote] = useState("");
  const form = useForm({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: "", email: "", password: "" },
  });

  return (
    <AuthLayout
      title="Create an account"
      footer={
        <p>
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit(async (values) => {
          setFormError("");
          try {
            const response = await api("/api/v1/auth/register", { method: "POST", body: JSON.stringify(values) });
            const body = await readJson<{ csrf_token: string; email_delivery: string }>(response);
            rememberCsrf(body.csrf_token);
            setNote(deliveryNote(body.email_delivery));
            await refresh();
            navigate("/overview");
          } catch (error) {
            setFormError(error instanceof ApiRequestError ? error.message : "Registration failed.");
          }
        })}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="register-username">Username</Label>
          <Input id="register-username" autoComplete="username" {...form.register("username")} />
          <FieldError message={form.formState.errors.username?.message} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="register-email">Email</Label>
          <Input id="register-email" type="email" autoComplete="email" {...form.register("email")} />
          <FieldError message={form.formState.errors.email?.message} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="register-password">Password</Label>
          <Input id="register-password" type="password" autoComplete="new-password" {...form.register("password")} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        <FieldError message={formError} />
        {note ? <p className="text-sm text-ink-secondary">{note}</p> : null}
        <Button type="submit">Create account</Button>
      </form>
    </AuthLayout>
  );
}

export function VerifyPage() {
  const [params] = useSearchParams();
  const [message, setMessage] = useState("Confirming this link…");
  const [started, setStarted] = useState(false);
  const token = params.get("token") ?? "";

  async function confirm() {
    setStarted(true);
    try {
      await readJson(await api("/api/v1/auth/verify", { method: "POST", body: JSON.stringify({ token }) }));
      setMessage("This email address is verified. You can sign in.");
    } catch (error) {
      setMessage(error instanceof ApiRequestError ? error.message : "This link could not be confirmed.");
    }
  }

  return (
    <AuthLayout
      title="Verify email"
      footer={
        <Link to="/login">Back to sign in</Link>
      }
    >
      <p className="text-sm text-ink-secondary">{token ? message : "This page needs a verification link."}</p>
      {token && !started ? (
        <Button className="mt-4" type="button" onClick={() => void confirm()}>
          Confirm email
        </Button>
      ) : null}
    </AuthLayout>
  );
}

export function ForgotPage() {
  const [message, setMessage] = useState("");
  const form = useForm({
    resolver: zodResolver(z.object({ email: z.string().email("Enter a valid email address.") })),
    defaultValues: { email: "" },
  });

  return (
    <AuthLayout title="Reset password" footer={<Link to="/login">Back to sign in</Link>}>
      <form
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit(async (values) => {
          const response = await api("/api/v1/auth/forgot-password", {
            method: "POST",
            body: JSON.stringify(values),
          });
          const body = await readJson<{ message: string; password_reset: string }>(response);
          setMessage(body.message);
        })}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="forgot-email">Email</Label>
          <Input id="forgot-email" type="email" autoComplete="email" {...form.register("email")} />
          <FieldError message={form.formState.errors.email?.message} />
        </div>
        {message ? <p className="text-sm text-ink-secondary">{message}</p> : null}
        <Button type="submit">Send reset link</Button>
      </form>
    </AuthLayout>
  );
}

export function ResetPage() {
  const [params] = useSearchParams();
  const [message, setMessage] = useState("");
  const token = params.get("token") ?? "";
  const form = useForm({
    resolver: zodResolver(z.object({ password })),
    defaultValues: { password: "" },
  });

  return (
    <AuthLayout title="Choose a new password" footer={<Link to="/login">Back to sign in</Link>}>
      <form
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await readJson(
              await api("/api/v1/auth/reset-password", {
                method: "POST",
                body: JSON.stringify({ token, password: values.password }),
              }),
            );
            setMessage("Password updated. Sign in with the new password.");
          } catch (error) {
            setMessage(error instanceof ApiRequestError ? error.message : "This link could not be used.");
          }
        })}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="reset-password">New password</Label>
          <Input id="reset-password" type="password" autoComplete="new-password" {...form.register("password")} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        {message ? <p className="text-sm text-ink-secondary">{message}</p> : null}
        <Button type="submit" disabled={!token}>
          Update password
        </Button>
      </form>
    </AuthLayout>
  );
}

export function UnlockPage() {
  const { refresh } = useSession();
  const [message, setMessage] = useState("");
  const form = useForm({
    resolver: zodResolver(z.object({ password: z.string().min(1, "Enter your password.") })),
    defaultValues: { password: "" },
  });

  return (
    <AuthLayout title="Session locked">
      <p className="mb-4 text-sm text-ink-secondary">
        SpendPilot locked this session after 15 minutes without activity. A background heartbeat does not keep it open.
      </p>
      <form
        className="flex flex-col gap-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await readJson(
              await api("/api/v1/auth/unlock", { method: "POST", body: JSON.stringify(values) }),
            );
            await refresh();
          } catch (error) {
            setMessage(error instanceof ApiRequestError ? error.message : "The session could not be unlocked.");
          }
        })}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="unlock-password">Password</Label>
          <Input id="unlock-password" type="password" autoComplete="current-password" {...form.register("password")} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        <FieldError message={message} />
        <Button type="submit">Unlock</Button>
      </form>
    </AuthLayout>
  );
}
