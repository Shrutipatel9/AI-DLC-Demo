import { CircleCheck, Circle } from "lucide-react";

import { PASSWORD_RULES } from "./schemas";

// Rule list shown before typing (WCAG 3.3.2); each rule ticks as it is met, with an icon
// and text so meaning never depends on colour alone.
export function PasswordRules({ value, id }: { value: string; id: string }) {
  return (
    <ul id={id} className="mt-1 space-y-1 text-sm" data-testid="password-rules">
      {PASSWORD_RULES.map((rule) => {
        const met = rule.test(value);
        return (
          <li
            key={rule.id}
            className={
              met ? "flex items-center gap-2 text-success" : "flex items-center gap-2 text-muted"
            }
            data-testid={`password-rule-${rule.id}`}
            data-met={met ? "true" : "false"}
          >
            {met ? (
              <CircleCheck aria-hidden="true" size={16} />
            ) : (
              <Circle aria-hidden="true" size={16} />
            )}
            <span>
              {rule.text}
              <span className="sr-only">{met ? " (met)" : " (not met yet)"}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
