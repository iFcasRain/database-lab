/*
  第三周 00：创建数据库
  说明：脚本不会删除已有数据库。若数据库已存在，只切换到该数据库。
*/

USE master;
GO

IF DB_ID(N'ConvenienceStoreDB') IS NULL
BEGIN
    CREATE DATABASE ConvenienceStoreDB;
    PRINT N'ConvenienceStoreDB 创建成功。';
END
ELSE
BEGIN
    PRINT N'ConvenienceStoreDB 已存在，本脚本未删除或覆盖它。';
END;
GO

USE ConvenienceStoreDB;
GO

SELECT
    DB_NAME() AS current_database,
    SUSER_SNAME() AS current_login,
    SYSDATETIME() AS checked_at;
GO
