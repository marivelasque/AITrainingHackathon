# auth.R ----------------------------------------------------------
# Login setup using shinymanager. Credentials are stored, hashed, in
# their own SQLite file, separate from the shop data.
#
# Demo credentials only. Before using this app with anything real,
# replace CREDENTIALS_PASSPHRASE and the sample accounts below.

library(shinymanager)

CREDENTIALS_DB_PATH  <- "data/credentials.sqlite"
CREDENTIALS_PASSPHRASE <- "hackathon-demo-passphrase"

# Each buyer gets their own budget, stored alongside their login.
DEMO_CREDENTIALS <- data.frame(
  user     = c("alice", "bob", "carla"),
  password = c("alice123", "bob123", "carla123"),
  budget   = c(5000, 3000, 8000),
  admin    = c(FALSE, FALSE, FALSE),
  stringsAsFactors = FALSE
)

#' Create the credentials database on first run only.
init_credentials_db <- function(path = CREDENTIALS_DB_PATH) {
  if (!file.exists(path)) {
    create_db(
      credentials_data = DEMO_CREDENTIALS,
      sqlite_path = path,
      passphrase = CREDENTIALS_PASSPHRASE
    )
  }
  invisible(TRUE)
}

#' Credential-check function passed to shinymanager::secure_server().
shop_check_credentials <- function(path = CREDENTIALS_DB_PATH) {
  check_credentials(path, passphrase = CREDENTIALS_PASSPHRASE)
}
