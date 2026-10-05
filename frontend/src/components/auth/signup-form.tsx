"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "@/components/feedback/toast";

import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { fieldMessage, messageFor } from "./messages";
import { PasswordRules } from "./password-rules";
import { signUpSchema, type SignUpValues } from "./schemas";

// Sign up (US3.1, WF-U1-1; mockups §2.1).
export function SignUpForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signUp } = useAuthActions();
  const [showPassword, setShowPassword] = useState(false);
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { fullName: "", email: searchParams.get("email") ?? "", password: "" },
    shouldFocusError: true,
  });
  const password = useWatch({ control, name: "password" });

  async function onSubmit(values: SignUpValues) {
    setAlreadyRegistered(false);
    try {
      await signUp(values);
      toast.success("We sent you a code. Check your email.");
      router.push("/verify");
    } catch (error) {
      if (!isApiError(error)) throw error;
      if (error.code === "VALIDATION_FAILED") {
        for (const [field, reason] of Object.entries(error.fieldErrors)) {
          if (field === "fullName" || field === "email" || field === "password") {
            setError(field, { message: fieldMessage(field, reason) }, { shouldFocus: true });
          }
        }
        return;
      }
      if (error.code === "EMAIL_ALREADY_REGISTERED") {
        setAlreadyRegistered(true);
        setError("email", { message: messageFor(error) }, { shouldFocus: true });
        return;
      }
      toast.error(messageFor(error));
    }
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      data-testid="signup-form"
    >
      <FormField id="fullName" label="Full name" error={errors.fullName?.message}>
        <Input
          id="fullName"
          autoComplete="name"
          readOnly={isSubmitting}
          aria-invalid={errors.fullName ? "true" : "false"}
          aria-describedby={describedBy("fullName", { error: Boolean(errors.fullName) })}
          data-testid="signup-fullname-input"
          {...register("fullName")}
        />
      </FormField>
      <FormField id="email" label="Email" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          readOnly={isSubmitting}
          aria-invalid={errors.email ? "true" : "false"}
          aria-describedby={describedBy("email", { error: Boolean(errors.email) })}
          data-testid="signup-email-input"
          {...register("email")}
        />
      </FormField>
      {alreadyRegistered ? (
        <p className="text-sm">
          <Link
            href="/login"
            className="font-semibold text-accent-strong underline"
            data-testid="signup-signin-instead-link"
          >
            Sign in instead
          </Link>
        </p>
      ) : null}
      <FormField
        id="password"
        label="Password"
        error={errors.password?.message}
        hint={<PasswordRules id="password-rules" value={password} />}
      >
        <div className="flex gap-2">
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            readOnly={isSubmitting}
            aria-invalid={errors.password ? "true" : "false"}
            aria-describedby={describedBy("password", {
              hint: true,
              error: Boolean(errors.password),
            })}
            data-testid="signup-password-input"
            {...register("password")}
          />
          <Button
            type="button"
            variant="secondary"
            onClick={() => setShowPassword((shown) => !shown)}
            aria-pressed={showPassword}
            aria-controls="password"
            data-testid="signup-password-toggle-button"
          >
            {showPassword ? "Hide" : "Show"}
          </Button>
        </div>
      </FormField>
      <Button type="submit" width="full" disabled={isSubmitting} data-testid="signup-submit-button">
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>
      <p className="text-center text-base">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-semibold text-accent-strong underline"
          data-testid="signup-login-link"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
