library ieee;
use ieee.std_logic_1164.all;

entity iso_b is
generic (
    ID      : natural
);
port (
    clock   : in std_logic;
    d       : in std_logic;
    q       : out std_logic
);
end entity iso_b;

architecture rtl of iso_b is
begin
    q <= d when rising_edge(clock);
end architecture rtl;
