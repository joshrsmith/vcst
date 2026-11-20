library ieee;
use ieee.std_logic_1164.all;

entity iso_a is
generic (
    ID      : natural
);
port (
    clock   : in std_logic;
    d       : in std_logic;
    q       : out std_logic
);
end entity iso_a;

architecture rtl of iso_a is
begin
    q <= d when rising_edge(clock);
end architecture rtl;
