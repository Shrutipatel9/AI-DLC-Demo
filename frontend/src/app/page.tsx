import { redirect } from "next/navigation";

// The landing page arrives in a later unit; until then the root goes to log in.
export default function RootPage() {
  redirect("/login");
}
