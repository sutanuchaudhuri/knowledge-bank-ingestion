import assert from "node:assert/strict";
import test from "node:test";

import { studentTokenFromRequest } from "../lib/studentCookie.mjs";

const request = (cookie) => new Request("http://localhost/", cookie ? { headers: { cookie } } : {});

test("reads the student token cookie from a plain request", () => {
  assert.equal(studentTokenFromRequest(request("a=1; mb_student_token=abc.def.ghi; b=2")), "abc.def.ghi");
  assert.equal(studentTokenFromRequest(request("mb_student_token=a%3Db")), "a=b");
});

test("returns null for an anonymous request", () => {
  assert.equal(studentTokenFromRequest(request()), null);
  assert.equal(studentTokenFromRequest(request("mb_admin_session=x")), null);
});
