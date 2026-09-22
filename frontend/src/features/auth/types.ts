export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}
export interface AuthSession {
  user: User;
  csrf_token: string;
  expires_at: string;
}
export interface Credentials {
  email: string;
  password: string;
}
export interface Registration extends Credentials {
  name: string;
}
