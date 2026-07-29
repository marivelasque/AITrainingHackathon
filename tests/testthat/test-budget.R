test_that("can_afford allows an order that exactly uses the remaining budget", {
  expect_true(can_afford(budget = 100, spent = 60, order_total = 40))
})

test_that("can_afford blocks an order that exceeds the remaining budget", {
  expect_false(can_afford(budget = 100, spent = 60, order_total = 40.01))
})

test_that("place_order records an order and updates spend", {
  con <- get_shop_con(":memory:")
  on.exit(dbDisconnect(con))
  init_shop_db(con)

  product <- get_products(con)[1, ]
  result <- place_order(con, "test_user", product$id, quantity = 2, budget = 1e6)

  expect_true(result$success)
  expect_equal(get_spent(con, "test_user"), product$price * 2)
  expect_equal(nrow(get_orders(con, "test_user")), 1)
})

test_that("place_order refuses an order over budget and does not record it", {
  con <- get_shop_con(":memory:")
  on.exit(dbDisconnect(con))
  init_shop_db(con)

  product <- get_products(con)[1, ]
  result <- place_order(
    con, "test_user", product$id, quantity = 1, budget = product$price - 1
  )

  expect_false(result$success)
  expect_equal(get_spent(con, "test_user"), 0)
  expect_equal(nrow(get_orders(con, "test_user")), 0)
})

test_that("place_order rejects an unknown product", {
  con <- get_shop_con(":memory:")
  on.exit(dbDisconnect(con))
  init_shop_db(con)

  result <- place_order(con, "test_user", product_id = 9999, quantity = 1, budget = 1e6)

  expect_false(result$success)
})

test_that("place_order rejects a quantity below 1", {
  con <- get_shop_con(":memory:")
  on.exit(dbDisconnect(con))
  init_shop_db(con)

  product <- get_products(con)[1, ]
  result <- place_order(con, "test_user", product$id, quantity = 0, budget = 1e6)

  expect_false(result$success)
})
