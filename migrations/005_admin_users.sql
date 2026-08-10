-- Multi-admin logins (shared bcrypt hashes from the other Helix app).

CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_admin_users_email ON admin_users (email);

INSERT INTO admin_users (id, name, email, password_hash) VALUES
    (gen_random_uuid(), 'Michael Owusu', 'michaelowusubudu@gmail.com', '$2a$10$yPa7L8jJ53VKyVE9BJSDkuND/U2cBbKsgNHP7ahR9gI3tAa/DZ986'),
    (gen_random_uuid(), 'Amin Yakubu', 'yakubuamin14@gmail.com', '$2a$10$.YkND3llEVdP/pQnYMzK9Of/JByeTCXNEF0vh88SvZFmxut6ssIO2'),
    (gen_random_uuid(), 'Nathaniel Aryee', 'briteaddae@gmail.com', '$2a$10$56rB3dHWARAFghNAwdhHqO1Aht22L6Ju7Nv1JM/LDRkf7.RO4SKEe'),
    (gen_random_uuid(), 'Hafez Mahamah', 'ahmahamah@gmail.com', '$2a$10$b3Ej64bAIlnAI980.4ZtYeCxRdQbSobZWRWxHNrETwh7JmV/C6Bzm'),
    (gen_random_uuid(), 'Mawuli Pomary', 'vivaqhojo@gmail.com', '$2a$10$JJ2yTRY7ldF5vAz8TSjhVuctO6RHwxVlR91mAN7sCColHDrP2A7cW'),
    (gen_random_uuid(), 'Dennis Boachie Boateng', 'dennisboachie9+helix@gmail.com', '$2a$10$EB6m5YfNkKPBWSx9sW2RledxGwzwlyC.oyxf05/nQSsEKCWzHqJDq'),
    (gen_random_uuid(), 'David Bentil', 'david.bentil@blvcksapphire.com', '$2a$10$CESFb23PJxkLx5L/fc/yBe/k4e0eWtYeopL7.PI.mDaY6WVe6RQfi'),
    (gen_random_uuid(), 'Prince Nedjoh', 'princenedjoh5+1@gmail.com', '$2a$10$71gM5g0ByKhqORqpGw03tu4D6znZg.SVx4L/38EFyQ/ODThza7fBW'),
    (gen_random_uuid(), 'Prince Nedjoh', 'princenedjoh5+4@gmail.com', '$2a$10$Tgk9rqwqOcA9CpEFzbebCeeUcaJViyM1hdZj6Dxrz.rT.wYd22Bd2'),
    (gen_random_uuid(), 'Prince Nedjoh', 'princenedjoh5+beta@gmail.com', '$2a$10$kH5T6v89fnksh74dGcbkT.ROBhw49BluhMzk48ruyXt4ve7YIJ0CS')
ON CONFLICT (email) DO NOTHING;
