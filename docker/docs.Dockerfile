FROM node:24-alpine AS development
WORKDIR /app
ENV TZ=Asia/Shanghai

COPY ./docs/package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

EXPOSE 5174

