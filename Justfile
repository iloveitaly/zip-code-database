# zsh is the default shell under macos, let's mirror it everywhere
set shell := ["zsh", "-ceuB", "-o", "pipefail"]

# for [script] support
set unstable := true

# determines what shell to use for [script]
# TODO can we force tracing and a custom PS4 prompt? Would be good to understand how Just handles echoing commands
set script-interpreter := ["zsh", "-euB", "-o", "pipefail"]

download-zipcode-population:
  # manually download the file
  open 'https://data.census.gov/table?q=B01003:+TOTAL+POPULATION&g=010XX00US$8600000'

  # wait for user confirmation
  @printf "Have you downloaded the file to %s? Press Enter to continue: " "${input_file:-$script_dir/data/raw_zip_code_with_population.csv}" >/dev/tty
  @read -r _ </dev/tty

  # then, after downloading, run this command
  python clean_zip_data.py

[script]
download-places:
  open 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip'
  # assume everything in this recipe is a zsh script

db-open:
  open "mysql://root@localhost:3306"