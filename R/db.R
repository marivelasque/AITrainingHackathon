# db.R ------------------------------------------------------------
# Shop database: products and orders. Kept independent of Shiny and of
# shinymanager so it can be unit tested with a plain SQLite connection.

library(DBI)
library(RSQLite)

SHOP_DB_PATH <- "data/shop.sqlite"

# Sample furniture catalogue used to seed a fresh database.
SEED_PRODUCTS <- data.frame(
  name        = c(
    "Bergen 3-Seater Sofa", "Kobe Armchair", "Nordvik Coffee Table",
    "Aalto Dining Table", "Lund Dining Chair", "Tromso Bookshelf",
    "Espen Wardrobe", "Skagen Bed Frame", "Halden Floor Lamp",
    "Rovaniemi Sideboard", "Malmo Bar Stool", "Kiruna TV Unit"
  ),
  category    = c(
    "Sofas", "Sofas", "Tables", "Tables", "Chairs", "Storage",
    "Storage", "Bedroom", "Lighting", "Storage", "Chairs", "Storage"
  ),
  price       = c(
    1299.00, 649.00, 249.00, 899.00, 129.00, 379.00,
    699.00, 999.00, 89.00, 549.00, 99.00, 429.00
  ),
  description = c(
    "Three-seater sofa in grey wool blend fabric.",
    "Compact armchair with oak legs.",
    "Round coffee table in solid oak.",
    "Extendable dining table, seats up to 8.",
    "Upholstered dining chair with beech frame.",
    "Five-shelf bookcase in white oak veneer.",
    "Two-door wardrobe with hanging rail and shelves.",
    "Queen-size bed frame with upholstered headboard.",
    "Adjustable floor lamp with linen shade.",
    "Sideboard with three drawers and cabinet storage.",
    "Counter-height bar stool with footrest.",
    "TV unit with cable management, fits up to 65-inch screens."
  ),
  colour      = c(
    "#8C6A5A", "#B08968", "#6B4F3B", "#5C4433", "#A47551",
    "#4A4A48", "#3E3E3C", "#7A5C61", "#C9A66B", "#5B4636",
    "#8C6A5A", "#3E3E3C"
  ),
  stringsAsFactors = FALSE
)

#' Open a connection to the shop database.
get_shop_con <- function(path = SHOP_DB_PATH) {
  dbConnect(SQLite(), dbname = path)
}

#' Create tables if missing and seed products on first run.
init_shop_db <- function(con) {
  if (!dbExistsTable(con, "products")) {
    products <- SEED_PRODUCTS
    products$id <- seq_len(nrow(products))
    dbWriteTable(con, "products", products)
  }

  if (!dbExistsTable(con, "orders")) {
    orders <- data.frame(
      id = integer(0), username = character(0), product_id = integer(0),
      product_name = character(0), quantity = integer(0),
      unit_price = numeric(0), order_total = numeric(0),
      ordered_at = character(0), stringsAsFactors = FALSE
    )
    dbWriteTable(con, "orders", orders)
  }

  invisible(TRUE)
}

#' All products in the catalogue.
get_products <- function(con) {
  dbGetQuery(con, "SELECT * FROM products ORDER BY category, name")
}

#' A single product by id, or NULL if it doesn't exist.
get_product <- function(con, product_id) {
  result <- dbGetQuery(
    con, "SELECT * FROM products WHERE id = ?", params = list(product_id)
  )
  if (nrow(result) == 0) NULL else result[1, ]
}

#' Orders placed by a given user, most recent first.
get_orders <- function(con, username) {
  dbGetQuery(
    con,
    "SELECT * FROM orders WHERE username = ? ORDER BY id DESC",
    params = list(username)
  )
}

#' Total already spent by a user (0 if they have no orders yet).
get_spent <- function(con, username) {
  result <- dbGetQuery(
    con,
    "SELECT COALESCE(SUM(order_total), 0) AS spent FROM orders WHERE username = ?",
    params = list(username)
  )
  result$spent[1]
}

#' Would this order fit within the user's remaining budget?
#' Pure function (no database, no Shiny) so it's simple to unit test.
can_afford <- function(budget, spent, order_total) {
  (spent + order_total) <= (budget + 1e-9)
}

#' Attempt to place an order. Returns a list with `success` (logical) and
#' `message` (character), so the caller can show it straight to the user.
place_order <- function(con, username, product_id, quantity, budget) {
  product <- get_product(con, product_id)
  if (is.null(product)) {
    return(list(success = FALSE, message = "That product no longer exists."))
  }
  if (is.na(quantity) || quantity < 1) {
    return(list(success = FALSE, message = "Enter a quantity of at least 1."))
  }

  order_total <- product$price * quantity
  spent <- get_spent(con, username)

  if (!can_afford(budget, spent, order_total)) {
    remaining <- budget - spent
    return(list(
      success = FALSE,
      message = sprintf(
        "That order is $%.2f but you only have $%.2f left in your budget.",
        order_total, remaining
      )
    ))
  }

  dbExecute(
    con,
    paste(
      "INSERT INTO orders",
      "(username, product_id, product_name, quantity, unit_price, order_total, ordered_at)",
      "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ),
    params = list(
      username, product_id, product$name, quantity, product$price,
      order_total, as.character(Sys.time())
    )
  )

  list(
    success = TRUE,
    message = sprintf("Order placed: %d x %s ($%.2f).", quantity, product$name, order_total)
  )
}
